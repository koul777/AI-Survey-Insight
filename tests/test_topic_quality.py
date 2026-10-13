from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import adjusted_rand_score

from survey_insight.models import TableData, Topic
from survey_insight.pipeline import analyze_table
from survey_insight.topics import (
    _coherence,
    _fit_nmf,
    _lda_input_diagnostics,
    _normalize_nmf_factors,
    _refit_candidate_labels,
)


class TopicNumericalQualityTests(unittest.TestCase):
    def test_bigram_does_not_count_as_a_third_word_for_lda_sufficiency(self) -> None:
        vectorizer = CountVectorizer(ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(["red apple", "blue berry", "red apple", "blue berry"])
        self.assertTrue(np.all(np.asarray((matrix > 0).sum(axis=1)).ravel() == 3))
        diagnostics = _lda_input_diagnostics(matrix, vectorizer)
        self.assertEqual(diagnostics["input_median_distinct_terms"], 2)
        self.assertFalse(diagnostics["input_evidence_sufficient"])
        self.assertEqual(diagnostics["input_term_count_unit"], "unigram")

    def test_non_cooccurring_singletons_are_not_perfectly_coherent(self) -> None:
        topic = Topic("T01", "words", "", 2, 1.0, ["alpha", "beta"], [])
        disjoint = CountVectorizer().fit(["alpha", "beta"])
        together = CountVectorizer().fit(["alpha beta", "alpha beta"])
        score_disjoint = _coherence(disjoint, disjoint.transform(["alpha", "beta"]), [topic], smoothing="jeffreys")
        score_together = _coherence(together, together.transform(["alpha beta", "alpha beta"]), [topic], smoothing="jeffreys")
        # The legacy ranking score stays unchanged; this is a separate diagnostic.
        self.assertEqual(_coherence(disjoint, disjoint.transform(["alpha", "beta"]), [topic]), 1.0)
        self.assertLess(score_disjoint, 0.5)
        self.assertGreater(score_together, score_disjoint)
        self.assertLess(score_together, 1.0)

    def test_nmf_assignments_do_not_depend_on_arbitrary_factor_scaling(self) -> None:
        original_weights = np.asarray([[0.9, 0.1], [0.2, 0.8], [0.51, 0.49], [0.3, 0.7]])
        original_components = np.asarray([[1.0, 0.0], [0.0, 1.0]])
        predictions = []
        for scale in [np.asarray([1.0, 1.0]), np.asarray([0.01, 100.0])]:
            fitted = Mock()
            fitted.fit_transform.return_value = original_weights * scale
            fitted.components_ = original_components / scale[:, None]
            with patch("survey_insight.topics.NMF", return_value=fitted):
                result = _fit_nmf(original_weights @ original_components, 2, 42)
            self.assertIsNotNone(result)
            labels, weights, components = result
            np.testing.assert_allclose(weights @ components, original_weights @ original_components)
            np.testing.assert_allclose(components.sum(axis=1), 1.0)
            np.testing.assert_allclose(weights / weights.sum(axis=1)[:, None], original_weights)
            predictions.append(labels)
        np.testing.assert_array_equal(predictions[0], predictions[1])
        np.testing.assert_array_equal(predictions[0], [0, 1, 0, 1])

    def test_zero_nmf_component_stays_finite_without_invented_weight(self) -> None:
        weights, components = _normalize_nmf_factors(
            np.asarray([[2.0, 3.0]]), np.asarray([[1.0, 1.0], [0.0, 0.0]])
        )
        self.assertTrue(np.isfinite(weights).all())
        self.assertTrue(np.isfinite(components).all())
        self.assertEqual(weights[0, 1], 0.0)
        np.testing.assert_allclose(weights @ components, [[2.0, 2.0]])

    def test_nmf_zero_evidence_row_is_an_outlier(self) -> None:
        fitted = Mock()
        fitted.fit_transform.return_value = np.asarray([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
        fitted.components_ = np.eye(2)
        with patch("survey_insight.topics.NMF", return_value=fitted):
            result = _fit_nmf(np.asarray([[1, 0], [0, 1], [0, 0]]), 2, 42)
        self.assertIsNotNone(result)
        np.testing.assert_array_equal(result[0], [0, 1, -1])

    def test_single_component_nmf_does_not_assign_empty_vector(self) -> None:
        result = _fit_nmf(np.asarray([[1, 0], [0, 0], [2, 1]]), 1, 42)
        np.testing.assert_array_equal(result[0], [0, -1, 0])
        self.assertEqual(result[1][1, 0], 0.0)
        np.testing.assert_allclose(result[2].sum(axis=1), 1.0)

    def test_resampling_keeps_minibatch_nmf_below_size_threshold(self) -> None:
        matrix = np.asarray([[1, 0], [0, 1], [1, 0], [0, 1]])
        with patch("survey_insight.topics._fit_nmf", return_value=None) as fit:
            _refit_candidate_labels("nmf_minibatch", matrix, matrix, None, 2, 42)
        self.assertIs(fit.call_args.kwargs["use_minibatch"], True)

    def test_resampling_keeps_minibatch_kmeans_below_size_threshold(self) -> None:
        matrix = np.asarray([[1, 0], [0, 1], [1, 0], [0, 1]])
        with patch("survey_insight.topics._cluster", return_value=None) as fit:
            _refit_candidate_labels("kmeans", matrix, matrix, None, 2, 42, use_minibatch=True)
        self.assertIs(fit.call_args.kwargs["use_minibatch"], True)


class TopicEvidenceIntegrationTests(unittest.TestCase):
    def test_topic_review_count_restores_duplicate_response_frequency(self) -> None:
        rows = [{"response": text} for text in [
            "교육이 좋다는 말에 동의하지 않습니다.",
            "교육이 좋다는 말에 동의하지 않습니다.",
            "교육이 유익합니다.",
        ]]
        package = analyze_table(TableData(["response"], rows), text_column="response", group_columns=[])
        self.assertEqual(sum(topic.count for topic in package.selected_topics), 3)
        self.assertEqual(sum(topic.sentiment_review_count for topic in package.selected_topics), 2)
        self.assertEqual(sum(bool(doc.sentiment.get("needs_review")) for doc in package.documents), 2)
        for topic in package.selected_topics:
            if topic.sentiment_review_count:
                self.assertIn("문맥 검토", topic.suggested_action)
                self.assertNotIn("확산", topic.suggested_action)
                self.assertIn("확정하지", topic.sentiment_plain_language)

    def test_low_overlap_language_does_not_claim_reliable_topics(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures/topic_paraphrases.json").read_text(encoding="utf-8"))
        rows = [{"response": text} for texts in fixture["topics"].values() for text in texts]
        package = analyze_table(TableData(["response"], rows), text_column="response", group_columns=[])
        candidate = package.recommendation.recommended
        self.assertEqual(candidate.params["result_quality_status"], "review_required")
        self.assertTrue(candidate.params["result_quality_reasons"])
        self.assertIn("coherence_smoothed", candidate.metrics)
        self.assertFalse(candidate.params["coherence_diagnostic_in_score"])
        self.assertEqual(len(package.assignments), len(rows))

    def test_imbalanced_topics_keep_minority_subject_and_observed_frequencies(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures/korean_analysis.json").read_text(encoding="utf-8"))
        rows = [
            {"response": text, "gold": subject}
            for subject, texts in fixture["topics"].items()
            for text in texts[:4 if subject == "시설" else 8]
        ]
        # Repeated answers increase reported frequency, not the modeling unit.
        repeated_rows = rows + rows[:8] * 3
        package = analyze_table(TableData(["response", "gold"], repeated_rows),
                                text_column="response", group_columns=[])
        assigned = {a.document_id: a.topic_id for a in package.assignments}
        self.assertGreaterEqual(adjusted_rand_score(
            [row["gold"] for row in repeated_rows], [assigned[doc.id] for doc in package.documents]), 0.9)
        self.assertEqual(len(package.selected_topics), 3)
        self.assertEqual(package.recommendation.analysis_diagnostics["model_fit_document_count"], len(rows))
        self.assertEqual(sorted(topic.count for topic in package.selected_topics), [4, 8, 32])
        self.assertEqual(sum(topic.count for topic in package.selected_topics), len(repeated_rows))


if __name__ == "__main__":
    unittest.main()
