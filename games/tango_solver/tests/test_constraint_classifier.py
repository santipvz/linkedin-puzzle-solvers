from __future__ import annotations

import numpy as np

from games.tango_solver.src.constraint_classifier import ConstraintClassifier


def test_constraint_classifier_recognizes_equals_and_not_equals() -> None:
    classifier = ConstraintClassifier()
    equals = np.full((30, 60, 3), 255, dtype=np.uint8)
    equals[12:15, 10:50] = [140, 114, 76]
    equals[18:21, 10:50] = [140, 114, 76]
    not_equals = np.full((40, 40, 3), 255, dtype=np.uint8)
    for index in range(20):
        not_equals[10 + index, 10 + index] = [140, 114, 76]
        not_equals[10 + index, 30 - index] = [140, 114, 76]

    assert classifier.classify_constraint(equals) == "equals"
    assert classifier.classify_constraint(not_equals) == "not_equals"


def test_constraint_classifier_rejects_empty_image() -> None:
    empty = np.zeros((50, 50, 3), dtype=np.uint8)

    assert ConstraintClassifier().classify_constraint(empty) is None
