from __future__ import annotations

import numpy as np
import pytest

from core.vision import CosineTemplateMatcher, DistanceWeightedKnn


def test_cosine_matcher_ranks_best_template_per_label() -> None:
    matcher = CosineTemplateMatcher(
        np.array([[1, 0], [0.9, 0.1], [0, 1]], dtype=np.float32),
        ["A", "A", "B"],
    )

    prediction = matcher.predict(np.array([1, 0], dtype=np.float32))

    assert prediction is not None
    assert prediction.value == "A"
    assert prediction.confidence == pytest.approx(1.0)
    assert [candidate.value for candidate in prediction.candidates] == ["A", "B"]


def test_cosine_matcher_rejects_invalid_features() -> None:
    with pytest.raises(ValueError):
        CosineTemplateMatcher(np.empty((0, 2), dtype=np.float32), [])


def test_cosine_matcher_predicts_multiple_queries_in_one_batch() -> None:
    matcher = CosineTemplateMatcher(np.eye(2, dtype=np.float32), ["A", "B"])

    predictions = matcher.predict_many(np.eye(2, dtype=np.float32))

    assert [prediction.value if prediction else None for prediction in predictions] == ["A", "B"]


def test_distance_weighted_knn_assigns_exact_match_probability() -> None:
    model = DistanceWeightedKnn(
        np.array([[0, 0], [1, 1], [2, 2]], dtype=np.float32),
        np.array([1, 2, 2], dtype=np.int32),
        n_neighbors=3,
    )

    probabilities = model.predict_proba(np.array([1, 1], dtype=np.float32))[0]

    class_probabilities = dict(zip(model.classes_.tolist(), probabilities.tolist()))
    assert class_probabilities[2] == pytest.approx(1.0)
    assert class_probabilities[1] == pytest.approx(0.0)
