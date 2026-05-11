"""Classifier intentionally stubbed until Visitor 2 is wired."""

import pytest

from src.constraints.classifier import classify


def test_classify_stub_raises():
    dummy = {"type": "Probabilistic"}
    with pytest.raises(NotImplementedError):
        classify(dummy)
