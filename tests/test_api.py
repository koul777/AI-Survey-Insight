from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import survey_insight.api as api_module
from survey_insight.api import _RUNS, _STORE, app
from survey_insight.cli import create_demo_workbook
from survey_insight.storage import StorageRepository


class ApiTests(unittest.TestCase):
    def test_analysis_error_response_does_not_expose_api_key(self) -> None:
        secret = "sk-live-secret-value-abcdef1234567890"
        with patch("survey_insight.api._get_table", return_value=object()), patch(
            "survey_insight.api.analyze_table",
            side_effect=RuntimeError(f"provider rejected {secret}"),
        ):
            response = TestClient(app).post(
                "/model-runs",
                json={
                    "dataset_id": "dataset_test",
                    "llm_provider": "openai",
                    "llm_api_key": secret,
                    "external_transfer_confirmed": True,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(secret, response.text)
        self.assertIn("분석을 완료하지 못했습니다", response.text)

    def test_export_path_rejects_untrusted_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(api_module, "_EXPORT_DIR", Path(tmp)):
            with self.assertRaises(HTTPException) as raised:
                api_module._safe_export_path("../../outside", "xlsx")
        self.assertEqual(getattr(raised.exception, "status_code", None), 400)

    def test_delete_apis_clean_linked_runs_and_exports_without_touching_other_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = StorageRepository(tmp_path / "app.db")
            export_dir = tmp_path / "exports"
            workbook_path = tmp_path / "demo.xlsx"
            create_demo_workbook(workbook_path)
            body = workbook_path.read_bytes()
            api_module._TABLES.clear()
            api_module._PROFILES.clear()
            api_module._RUNS.clear()
            try:
                with patch.object(api_module, "_STORE", store), patch.object(api_module, "_EXPORT_DIR", export_dir):
                    client = TestClient(app)
                    first_upload = client.post("/datasets/upload?filename=first.xlsx", content=body).json()
                    second_upload = client.post("/datasets/upload?filename=second.xlsx", content=body).json()
                    first_run = client.post(
                        "/model-runs", json={"dataset_id": first_upload["dataset_id"]}
                    ).json()["run_id"]
                    second_run = client.post(
                        "/model-runs", json={"dataset_id": second_upload["dataset_id"]}
                    ).json()["run_id"]
                    created = client.post("/exports", json={"run_id": first_run, "type": "excel"})
                    export_path = Path(created.json()["file_path"])
                    other_created = client.post("/exports", json={"run_id": second_run, "type": "word"})
                    other_export_path = Path(other_created.json()["file_path"])
                    self.assertTrue(export_path.exists())
                    self.assertTrue(other_export_path.exists())

                    deleted_run = client.delete(f"/model-runs/{first_run}")
                    self.assertEqual(deleted_run.status_code, 200)
                    self.assertFalse(export_path.exists())
                    self.assertTrue(other_export_path.exists())
                    self.assertIsNone(store.get_run(first_run))
                    self.assertIsNotNone(store.get_run(second_run))
                    self.assertEqual(client.delete(f"/model-runs/{first_run}").status_code, 404)

                    blocked = client.delete(f"/datasets/{second_upload['dataset_id']}")
                    self.assertEqual(blocked.status_code, 409)
                    cascaded = client.delete(
                        f"/datasets/{second_upload['dataset_id']}?delete_runs=true"
                    )
                    self.assertEqual(cascaded.status_code, 200)
                    self.assertEqual(cascaded.json()["deleted_run_ids"], [second_run])
                    self.assertFalse(other_export_path.exists())
                    self.assertIsNone(store.get_dataset(second_upload["dataset_id"]))
                    self.assertIsNotNone(store.get_dataset(first_upload["dataset_id"]))
                    self.assertEqual(client.delete("/datasets/dataset_missing").status_code, 404)
            finally:
                api_module._TABLES.clear()
                api_module._PROFILES.clear()
                api_module._RUNS.clear()

    def test_web_ui_and_export_download_flow(self) -> None:
        client = TestClient(app)
        api_key = "sk-test-not-stored"
        ui = client.get("/")
        self.assertEqual(ui.status_code, 200)
        self.assertIn("text/html", ui.headers["content-type"])
        self.assertIn("fileInput", ui.text)
        self.assertIn("Excel 생성", ui.text)
        with tempfile.TemporaryDirectory() as tmp:
            workbook_path = Path(tmp) / "demo.xlsx"
            create_demo_workbook(workbook_path)
            upload = client.post(
                "/datasets/upload?filename=demo.xlsx",
                content=workbook_path.read_bytes(),
                headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
        self.assertEqual(upload.status_code, 200)
        upload_payload = upload.json()
        profile = upload_payload["profile"]
        self.assertEqual(profile["row_count"], 94)
        self.assertEqual(profile["column_count"], 63)
        run = client.post(
            "/model-runs",
            json={
                "dataset_id": upload_payload["dataset_id"],
                "project_name": "API UI Test",
                "text_column": profile["recommended_text_columns"][0]["column_name"],
                "group_columns": ["부서", "직종"],
                "llm_provider": "openai",
                "llm_api_key": api_key,
                "external_transfer_confirmed": True,
            },
        )
        self.assertEqual(run.status_code, 200)
        run_payload = run.json()
        self.assertEqual(run_payload["recommendation"]["valid_response_count"], 16)
        self.assertNotIn("visual_url", run_payload["recommendation"])
        stored_run = _STORE.get_run(run_payload["run_id"])
        self.assertIsNotNone(stored_run)
        self.assertEqual(stored_run.dataset_id, upload_payload["dataset_id"])
        stored_package = stored_run.to_analysis_package()
        self.assertEqual(stored_package.dataset_profile.dataset_id, upload_payload["dataset_id"])
        self.assertTrue(stored_package.project["llm_api_key_provided"])
        self.assertTrue(stored_package.project["external_transfer_confirmed"])
        self.assertEqual(stored_package.project["llm_interpretation_status"], "local_fallback")
        self.assertTrue(stored_package.project["llm_interpretation_warnings"])
        self.assertTrue(stored_package.recommendation.plain_language_summary)
        self.assertTrue(stored_package.recommendation.quality_warnings)
        self.assertNotIn(api_key, str(stored_run.package_json))
        self.assertNotIn(api_key, run.text)
        self.assertNotIn(api_key.encode(), _STORE.db_path.read_bytes())
        recent = client.get("/projects/recent")
        self.assertEqual(recent.status_code, 200)
        recent_projects = recent.json()["projects"]
        self.assertTrue(any(project["run_id"] == run_payload["run_id"] for project in recent_projects))
        expected_types = {
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "powerpoint": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        for export_type, media_type in expected_types.items():
            export = client.post("/exports", json={"run_id": run_payload["run_id"], "type": export_type})
            self.assertEqual(export.status_code, 200)
            download_url = export.json()["download_url"]
            download = client.get(download_url)
            self.assertEqual(download.status_code, 200)
            self.assertGreater(len(download.content), 1000)
            self.assertIn(media_type, download.headers["content-type"])
            with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                expanded = b"".join(archive.read(name) for name in archive.namelist())
            self.assertNotIn(api_key.encode(), expanded)

    def test_structural_edits_are_visible_in_read_endpoints(self) -> None:
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmp:
            workbook_path = Path(tmp) / "demo.xlsx"
            create_demo_workbook(workbook_path)
            upload = client.post("/datasets/upload?filename=demo.xlsx", content=workbook_path.read_bytes())
        run = client.post("/model-runs", json={"dataset_id": upload.json()["dataset_id"]})
        run_payload = run.json()
        run_id = run_payload["run_id"]
        excluded_topic_id = run_payload["recommendation"]["recommended"]["topics"][0]["topic_id"]
        _RUNS.pop(run_id, None)
        approval = client.post(
            f"/model-runs/{run_id}/edits",
            json={
                "edit_type": "record_review",
                "payload": {"decision": "approved", "notes": "라벨과 대표 응답 확인"},
                "user_id": "reviewer-1",
            },
        )
        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.json()["human_review"]["status"], "approved")
        edit = client.post(
            f"/model-runs/{run_id}/edits",
            json={"edit_type": "exclude_topic", "payload": {"topic_id": excluded_topic_id}, "user_id": "tester"},
        )
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.json()["human_review"]["status"], "changes_pending_review")
        reread = client.get(f"/model-runs/{run_id}/recommendation")
        self.assertEqual(reread.status_code, 200)
        reread_recommended = reread.json()["recommended"]
        topic_ids = [topic["topic_id"] for topic in reread_recommended["topics"]]
        self.assertNotIn(excluded_topic_id, topic_ids)
        self.assertEqual(reread_recommended["topic_count"], len(topic_ids))
        matching_candidate = next(
            candidate
            for candidate in reread.json()["candidates"]
            if candidate["candidate_id"] == reread_recommended["candidate_id"]
        )
        self.assertEqual(matching_candidate["topic_count"], len(topic_ids))
        self.assertEqual(len(matching_candidate["topics"]), len(topic_ids))
        recent = client.get("/projects/recent").json()["projects"]
        matching = next(project for project in recent if project["run_id"] == run_id)
        self.assertEqual(matching["recommended_topic_count"], len(topic_ids))
        self.assertEqual(matching["human_review_status"], "changes_pending_review")

    def test_external_provider_key_requires_transfer_confirmation(self) -> None:
        with patch("survey_insight.api._get_table", return_value=object()), patch(
            "survey_insight.api.analyze_table"
        ) as analyze:
            response = TestClient(app).post(
                "/model-runs",
                json={
                    "dataset_id": "dataset_test",
                    "llm_provider": "openai",
                    "llm_api_key": "sk-placeholder-value",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("외부 AI 전송 안내", response.text)
        analyze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
