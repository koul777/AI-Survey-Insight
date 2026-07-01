from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from survey_insight.api import _RUNS, _STORE, app
from survey_insight.cli import create_demo_workbook


class ApiTests(unittest.TestCase):
    def test_web_ui_and_export_download_flow(self) -> None:
        client = TestClient(app)
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
                "llm_api_key": "sk-test-not-stored",
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
        self.assertEqual(stored_package.project["llm_interpretation_status"], "local_fallback")
        self.assertTrue(stored_package.project["llm_interpretation_warnings"])
        self.assertTrue(stored_package.recommendation.plain_language_summary)
        self.assertTrue(stored_package.recommendation.quality_warnings)
        self.assertNotIn("sk-test-not-stored", str(stored_run.package_json))
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
        edit = client.post(
            f"/model-runs/{run_id}/edits",
            json={"edit_type": "exclude_topic", "payload": {"topic_id": excluded_topic_id}, "user_id": "tester"},
        )
        self.assertEqual(edit.status_code, 200)
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


if __name__ == "__main__":
    unittest.main()
