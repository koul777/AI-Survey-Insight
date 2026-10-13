from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from survey_insight import local_embeddings


class LocalEmbeddingTests(unittest.TestCase):
    def test_missing_model_never_downloads_during_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(local_embeddings, "local_model_path", return_value=Path(tmp)):
            with patch.object(local_embeddings, "_load_model") as load:
                result = local_embeddings.embed_texts_locally(["한국어 설문"])
        load.assert_not_called()
        self.assertEqual(result.vectors.size, 0)
        self.assertTrue(result.warnings)

    def test_encoder_uses_clustering_prefix_and_validates_shape(self) -> None:
        model = Mock()
        model.tokenizer.encode.return_value = [1, 2]
        model.encode.return_value = np.asarray([[1.0, 0.0], [0.0, 1.0]])
        with patch.object(local_embeddings, "local_embedding_status", return_value={"available": True}), patch.object(local_embeddings, "_load_model", return_value=model):
            result = local_embeddings.embed_texts_locally(["급여", "보수"])
        self.assertEqual(result.source, "local_sentence_transformer")
        self.assertEqual(model.encode.call_args.args[0], ["query: 급여", "query: 보수"])
        self.assertTrue(model.encode.call_args.kwargs["normalize_embeddings"])

    def test_encoder_failure_is_explicit_fallback(self) -> None:
        with patch.object(local_embeddings, "local_embedding_status", return_value={"available": True}), patch.object(local_embeddings, "_load_model", side_effect=ValueError("sensitive local path")):
            result = local_embeddings.embed_texts_locally(["응답"])
        self.assertEqual(result.vectors.size, 0)
        self.assertNotIn("sensitive local path", str(result.warnings))

    def test_long_document_preserves_all_chunks(self) -> None:
        model = Mock()
        model.tokenizer.encode.return_value = list(range(600))
        model.tokenizer.decode.return_value = "긴 응답의 일부"
        model.encode.return_value = np.asarray([[1.0, 0.0], [0.0, 1.0]])
        with patch.object(local_embeddings, "local_embedding_status", return_value={"available": True}), patch.object(local_embeddings, "_load_model", return_value=model):
            result = local_embeddings.embed_texts_locally(["긴 응답"])
        self.assertEqual(result.vectors.shape, (1, 2))
        self.assertEqual(result.diagnostics["encoded_chunks"], 2)
        self.assertGreater(result.vectors[0, 1], 0)
        self.assertAlmostEqual(float(np.linalg.norm(result.vectors[0])), 1.0)

    def test_setup_respects_offline_flag(self) -> None:
        with patch.dict("os.environ", {"SURVEY_INSIGHT_DISABLE_NETWORK": "1"}):
            with self.assertRaises(RuntimeError):
                local_embeddings.download_local_model()
