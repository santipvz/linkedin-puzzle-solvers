from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

import numpy as np


LabelT = TypeVar("LabelT")


@dataclass(frozen=True, slots=True)
class OcrCandidate(Generic[LabelT]):
    value: LabelT
    confidence: float


@dataclass(frozen=True, slots=True)
class OcrPrediction(Generic[LabelT]):
    value: LabelT
    confidence: float
    candidates: tuple[OcrCandidate[LabelT], ...]


class CosineTemplateMatcher(Generic[LabelT]):
    def __init__(self, features: np.ndarray, labels: Sequence[LabelT]) -> None:
        feature_array = np.asarray(features, dtype=np.float32)
        if feature_array.ndim != 2 or feature_array.shape[0] == 0 or feature_array.shape[1] == 0:
            raise ValueError("OCR template features must be a non-empty matrix.")
        if feature_array.shape[0] != len(labels):
            raise ValueError("OCR template feature and label counts must match.")
        if not np.all(np.isfinite(feature_array)):
            raise ValueError("OCR template features must be finite.")
        norms = np.linalg.norm(feature_array, axis=1)
        if np.any(norms <= 0.0):
            raise ValueError("OCR template features cannot contain empty rows.")
        self._features = feature_array / norms[:, None]
        self._labels = tuple(labels)

    def predict(self, feature: np.ndarray, *, limit: int = 5) -> OcrPrediction[LabelT] | None:
        flattened = np.asarray(feature, dtype=np.float32).reshape(-1)
        if flattened.size != self._features.shape[1] or not np.all(np.isfinite(flattened)):
            raise ValueError("OCR query feature has an invalid shape or values.")
        norm = float(np.linalg.norm(flattened))
        if norm <= 0.0:
            return None
        return self._prediction_from_scores(self._features @ (flattened / norm), limit=limit)

    def predict_many(self, features: np.ndarray, *, limit: int = 5) -> tuple[OcrPrediction[LabelT] | None, ...]:
        queries = np.asarray(features, dtype=np.float32)
        if queries.ndim != 2 or queries.shape[1] != self._features.shape[1] or not np.all(np.isfinite(queries)):
            raise ValueError("OCR query features have an invalid shape or values.")
        norms = np.linalg.norm(queries, axis=1)
        normalized = queries / np.maximum(norms[:, None], 1e-12)
        score_matrix = normalized @ self._features.T
        return tuple(
            None if norms[index] <= 0.0 else self._prediction_from_scores(scores, limit=limit)
            for index, scores in enumerate(score_matrix)
        )

    def _prediction_from_scores(self, scores: np.ndarray, *, limit: int) -> OcrPrediction[LabelT]:
        best_by_label: dict[LabelT, float] = {}
        for label, score in zip(self._labels, scores):
            best_by_label[label] = max(float(score), best_by_label.get(label, float("-inf")))
        ranked = sorted(best_by_label.items(), key=lambda item: item[1], reverse=True)
        candidates = tuple(
            OcrCandidate(value=label, confidence=score)
            for label, score in ranked[: max(1, int(limit))]
        )
        return OcrPrediction(
            value=candidates[0].value,
            confidence=candidates[0].confidence,
            candidates=candidates,
        )


class DistanceWeightedKnn:
    def __init__(self, features: np.ndarray, labels: np.ndarray, n_neighbors: int = 3) -> None:
        self._features = np.asarray(features, dtype=np.float32)
        self._labels = np.asarray(labels, dtype=np.int32)
        if self._features.ndim != 2 or self._labels.ndim != 1 or len(self._features) != len(self._labels):
            raise ValueError("KNN feature and label arrays have incompatible shapes.")
        if len(self._labels) == 0:
            raise ValueError("KNN requires at least one training sample.")
        self._n_neighbors = max(1, min(int(n_neighbors), len(self._labels)))
        self.classes_ = np.unique(self._labels)
        self._class_index = {int(value): index for index, value in enumerate(self.classes_)}

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        query_features = np.asarray(features, dtype=np.float32)
        if query_features.ndim == 1:
            query_features = query_features.reshape(1, -1)
        if query_features.ndim != 2 or query_features.shape[1] != self._features.shape[1]:
            raise ValueError("KNN query features have an incompatible shape.")

        probabilities = np.zeros((len(query_features), len(self.classes_)), dtype=np.float32)
        for row_index, feature in enumerate(query_features):
            distances = np.sum((self._features - feature) ** 2, axis=1)
            nearest = np.argpartition(distances, self._n_neighbors - 1)[: self._n_neighbors]
            nearest = nearest[np.argsort(distances[nearest])]
            nearest_distances = distances[nearest]
            nearest_labels = self._labels[nearest]
            exact_matches = nearest_distances <= 1e-12
            weights = exact_matches.astype(np.float32) if np.any(exact_matches) else 1.0 / (np.sqrt(nearest_distances) + 1e-6)
            for label, weight in zip(nearest_labels, weights):
                probabilities[row_index, self._class_index[int(label)]] += float(weight)
            total = float(np.sum(probabilities[row_index]))
            if total > 0.0:
                probabilities[row_index] /= total
        return probabilities
