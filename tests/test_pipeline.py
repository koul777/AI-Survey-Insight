from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from openpyxl import load_workbook

from survey_insight.cli import create_demo_workbook
from survey_insight.edits import apply_edit
from survey_insight.embeddings import EmbeddingResult
from survey_insight.exports import export_excel, export_powerpoint, export_word
from survey_insight.pipeline import analyze_file
from survey_insight.preprocessing import is_no_opinion, mask_pii, tokenize_keywords, tokenizer_source
from survey_insight.topics import _silhouette


class PipelineTests(unittest.TestCase):
    def test_prd_like_fixture_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workbook_path = tmp_path / "demo.xlsx"
            create_demo_workbook(workbook_path)
            package = analyze_file(workbook_path, project_name="Fixture")
            self.assertEqual(package.dataset_profile.row_count, 94)
            self.assertEqual(package.dataset_profile.column_count, 63)
            self.assertEqual(package.text_column, "15. 인사제도 개선을 위한 기타 건의 사항 [의견]")
            text_profile = next(
                col for col in package.dataset_profile.columns if col.column_name == package.text_column
            )
            self.assertGreaterEqual(text_profile.text_score, 0.70)
            self.assertEqual(package.recommendation.valid_response_count, 16)
            self.assertEqual(package.recommendation.mode, "소표본 모드")
            self.assertGreaterEqual(package.recommendation.recommended.topic_count, 2)
            self.assertLessEqual(package.recommendation.recommended.topic_count, 4)
            self.assertIsNotNone(package.recommendation.detailed)
            engines = {candidate.params["engine"] for candidate in package.recommendation.candidates}
            self.assertIn("kmeans", engines)
            self.assertIn("nmf", engines)
            self.assertIn("lda", engines)
            self.assertTrue(package.recommendation.plain_language_summary)
            self.assertIn("유효 자유응답", package.recommendation.plain_language_summary)
            self.assertIn("함께 비교", package.recommendation.topic_count_explanation)
            self.assertTrue(package.recommendation.methodology_plain_language)
            self.assertTrue(package.recommendation.quality_warnings)
            self.assertIn("tokenizer", package.recommendation.recommended.params)
            self.assertEqual(package.selected_topics[0].sentiment_method, "rule_lexicon_fallback")
            self.assertTrue(package.selected_topics[0].plain_language_summary)
            self.assertTrue(package.selected_topics[0].suggested_action)
            self.assertTrue(package.selected_topics[0].sentiment_plain_language)
            package.documents[0].original_text = "연락처는 privacy@example.com 입니다."
            package.documents[0].redacted_text = "연락처는 [EMAIL] 입니다."
            excel_path = export_excel(package, tmp_path / "report.xlsx")
            word_path = export_word(package, tmp_path / "report.docx")
            ppt_path = export_powerpoint(package, tmp_path / "report.pptx")
            self.assertTrue(excel_path.exists())
            self.assertTrue(word_path.exists())
            self.assertTrue(ppt_path.exists())
            workbook = load_workbook(excel_path)
            self.assertIn("토픽요약", workbook.sheetnames)
            assigned_sheet = workbook["원자료_토픽배정"]
            assigned_headers = [cell.value for cell in assigned_sheet[1]]
            self.assertNotIn("original_text", assigned_headers)
            self.assertIn("redacted_text", assigned_headers)
            assigned_values = " ".join(str(cell.value or "") for row in assigned_sheet.iter_rows() for cell in row)
            self.assertNotIn("privacy@example.com", assigned_values)
            self.assertIn("[EMAIL]", assigned_values)
            with zipfile.ZipFile(word_path) as zf:
                self.assertIn("word/document.xml", zf.namelist())
            with zipfile.ZipFile(ppt_path) as zf:
                self.assertIn("ppt/presentation.xml", zf.namelist())

    def test_preprocessing_privacy_and_no_opinion(self) -> None:
        self.assertTrue(is_no_opinion("해당 없음"))
        self.assertTrue(is_no_opinion("."))
        masked, found = mask_pii("연락처는 010-1234-5678 test@example.com 입니다.")
        self.assertIn("phone", found)
        self.assertIn("email", found)
        self.assertIn("[PHONE]", masked)
        self.assertIn("[EMAIL]", masked)

    def test_kiwi_noun_tokenizer_extracts_korean_nouns(self) -> None:
        self.assertEqual(tokenizer_source(), "kiwi_noun_extractor")
        tokens = tokenize_keywords("평가 기준이 어렵습니다. 인사제도 개선이 필요합니다.")
        self.assertIn("평가", tokens)
        self.assertIn("기준", tokens)
        self.assertIn("인사", tokens)
        self.assertIn("제도", tokens)
        self.assertNotIn("어렵습니다", tokens)

    def test_invalid_silhouette_candidate_gets_zero_separation_score(self) -> None:
        matrix = np.asarray([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]])
        labels = np.asarray([0, 0, 0])
        self.assertEqual(_silhouette(matrix, labels), 0.0)

    def test_user_edit_is_recorded_and_export_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workbook_path = Path(tmp) / "demo.xlsx"
            create_demo_workbook(workbook_path)
            package = analyze_file(workbook_path)
            topic_id = package.selected_topics[0].topic_id
            edit = apply_edit(
                package,
                "rename_topic",
                {"topic_id": topic_id, "label": "평가와 보상", "summary": "평가/보상 관련 개선 요구"},
                user_id="tester",
            )
            self.assertEqual(edit.edit_type, "rename_topic")
            self.assertEqual(package.selected_topics[0].label, "평가와 보상")
            self.assertEqual(len(package.user_edits), 1)

    def test_user_key_embedding_candidates_join_topic_count_competition(self) -> None:
        def fake_embeddings(texts: list[str], provider: str | None, api_key: str | None, **_: object) -> EmbeddingResult:
            vectors = np.asarray(
                [[1.0, 0.0, 0.0] if idx < len(texts) / 2 else [0.0, 1.0, 0.0] for idx, _ in enumerate(texts)],
                dtype=float,
            )
            return EmbeddingResult(
                vectors=vectors,
                source="openai_embeddings",
                model="fake-embedding-model",
                warnings=[],
            )

        with tempfile.TemporaryDirectory() as tmp:
            workbook_path = Path(tmp) / "demo.xlsx"
            create_demo_workbook(workbook_path)
            with patch("survey_insight.topics.embed_texts_with_provider", side_effect=fake_embeddings):
                package = analyze_file(
                    workbook_path,
                    embedding_provider="openai",
                    embedding_api_key="sk-realistic-key-for-test-without-network",
                )

        engines = {candidate.params["engine"] for candidate in package.recommendation.candidates}
        self.assertIn("openai_embedding_kmeans", engines)
        embedding_candidates = [
            candidate
            for candidate in package.recommendation.candidates
            if candidate.params["engine"].startswith("openai_embedding")
        ]
        self.assertTrue(embedding_candidates)
        self.assertTrue(all(candidate.params["embedding_model"] == "fake-embedding-model" for candidate in embedding_candidates))


if __name__ == "__main__":
    unittest.main()
