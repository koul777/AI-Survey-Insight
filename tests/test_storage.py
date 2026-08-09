from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from survey_insight.models import (
    AnalysisPackage,
    CandidateSolution,
    ColumnProfile,
    DatasetProfile,
    Recommendation,
    TextDocument,
    Topic,
    TopicAssignment,
)
from survey_insight.storage import StorageRepository


class StorageRepositoryTests(unittest.TestCase):
    def test_dataset_bytes_metadata_and_profile_survive_new_repository_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "nested" / "app.db"
            profile = _profile()
            body = b"name,feedback\nA,Needs clearer onboarding\n"

            repo = StorageRepository(db_path)
            saved = repo.save_dataset(
                data=body,
                filename="survey.csv",
                content_type="text/csv",
                profile=profile,
                metadata={"sheet_name": "Responses", "uploaded_by": "tester"},
            )

            self.assertEqual(saved.dataset_id, "dataset_test")
            self.assertEqual(saved.byte_size, len(body))

            reopened = StorageRepository(db_path)
            loaded = reopened.get_dataset("dataset_test")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.data, body)
            self.assertEqual(loaded.filename, "survey.csv")
            self.assertEqual(loaded.content_type, "text/csv")
            self.assertEqual(loaded.metadata_json["uploaded_by"], "tester")
            self.assertEqual(loaded.profile_json["row_count"], 1)
            self.assertEqual(loaded.to_profile().columns[0].column_name, "feedback")
            self.assertEqual([item.dataset_id for item in reopened.list_datasets()], ["dataset_test"])

    def test_completed_run_package_survives_new_repository_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.db"
            package = _analysis_package()

            repo = StorageRepository(db_path)
            repo.save_run(package=package, metadata={"status": "complete"})

            reopened = StorageRepository(db_path)
            loaded = reopened.get_run("run_test")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.dataset_id, "dataset_test")
            self.assertEqual(loaded.metadata_json["status"], "complete")
            self.assertEqual(loaded.package_json["recommendation"]["run_id"], "run_test")
            self.assertEqual(loaded.package_json["selected_topics"][0]["label"], "Onboarding")

            restored = loaded.to_analysis_package()
            self.assertIsInstance(restored, AnalysisPackage)
            self.assertEqual(restored.recommendation.allowed_topic_range, (1, 3))
            self.assertEqual(restored.selected_topics[0].topic_id, "T01")
            self.assertEqual(restored.assignments[0].document_id, "doc_1")
            self.assertEqual([item.run_id for item in reopened.list_runs("dataset_test")], ["run_test"])

    def test_delete_run_removes_only_requested_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = StorageRepository(Path(tmp) / "app.db")
            package = _analysis_package()
            repo.save_run(package=package, run_id="run_test", dataset_id="dataset_test")
            repo.save_run(package=package, run_id="run_other", dataset_id="dataset_other")

            deleted = repo.delete_run("run_test")

            self.assertTrue(deleted.deleted)
            self.assertIsNone(repo.get_run("run_test"))
            self.assertIsNotNone(repo.get_run("run_other"))
            self.assertFalse(repo.delete_run("run_missing").deleted)

    def test_dataset_delete_is_blocked_until_cascade_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = StorageRepository(Path(tmp) / "app.db")
            profile = _profile()
            repo.save_dataset(data=b"feedback\nhello\n", filename="survey.csv", profile=profile)
            repo.save_dataset(
                data=b"feedback\nkeep\n",
                filename="other.csv",
                profile=profile,
                dataset_id="dataset_other",
            )
            package = _analysis_package()
            repo.save_run(package=package, run_id="run_test", dataset_id="dataset_test")
            repo.save_run(package=package, run_id="run_other", dataset_id="dataset_other")

            blocked = repo.delete_dataset("dataset_test")
            self.assertFalse(blocked.deleted)
            self.assertEqual(blocked.blocked_by_run_ids, ("run_test",))
            self.assertIsNotNone(repo.get_dataset("dataset_test"))

            deleted = repo.delete_dataset("dataset_test", delete_runs=True)
            self.assertTrue(deleted.deleted)
            self.assertEqual(deleted.deleted_run_ids, ("run_test",))
            self.assertIsNone(repo.get_dataset("dataset_test"))
            self.assertIsNone(repo.get_run("run_test"))
            self.assertIsNotNone(repo.get_dataset("dataset_other"))
            self.assertIsNotNone(repo.get_run("run_other"))
            self.assertFalse(repo.delete_dataset("dataset_missing").deleted)


def _profile() -> DatasetProfile:
    column = ColumnProfile(
        column_name="feedback",
        detected_type="Free-text Response",
        confidence=0.95,
        missing_rate=0.0,
        unique_rate=1.0,
        text_score=0.9,
        reasons=["long text"],
        signals={"LengthSignal": 1.0},
        sample_values=["Needs clearer onboarding"],
    )
    return DatasetProfile(
        dataset_id="dataset_test",
        sheet_name="Responses",
        row_count=1,
        column_count=1,
        header_row_index=0,
        columns=[column],
        recommended_text_columns=[column],
    )


def _analysis_package() -> AnalysisPackage:
    topic = Topic(
        topic_id="T01",
        label="Onboarding",
        summary="Responses mention onboarding clarity.",
        count=1,
        share=1.0,
        keywords=["onboarding", "clarity"],
        representative_responses=["Needs clearer onboarding"],
    )
    assignment = TopicAssignment(
        document_id="doc_1",
        topic_id="T01",
        probability=1.0,
        is_outlier=False,
        assignment_source="model",
    )
    candidate = CandidateSolution(
        candidate_id="candidate_test",
        topic_count=1,
        params={"engine": "test"},
        metrics={"stability": 1.0, "coverage": 1.0},
        score=1.0,
        rank=1,
        topics=[topic],
        assignments=[assignment],
    )
    recommendation = Recommendation(
        run_id="run_test",
        mode="test",
        valid_response_count=1,
        allowed_topic_range=(1, 3),
        minimum_topic_size=1,
        recommended=candidate,
        wider=None,
        detailed=None,
        candidates=[candidate],
    )
    document = TextDocument(
        id="doc_1",
        row_index=0,
        text_column="feedback",
        original_text="Needs clearer onboarding",
        redacted_text="Needs clearer onboarding",
        metadata={"team": "Support"},
    )
    return AnalysisPackage(
        project={"name": "Storage Test"},
        dataset_profile=_profile(),
        text_column="feedback",
        group_columns=["team"],
        documents=[document],
        recommendation=recommendation,
        selected_candidate_id="candidate_test",
        selected_topics=[topic],
        assignments=[assignment],
        cross_analysis=[
            {
                "group_column": "team",
                "group_value": "Support",
                "topic_id": "T01",
                "topic_label": "Onboarding",
                "count": 1,
                "share": 1.0,
                "display_count": None,
                "suppressed": True,
            }
        ],
    )


if __name__ == "__main__":
    unittest.main()
