import pytest

from service import fine_tuning


def test_train_validation_overlap_rejected():
    with pytest.raises(ValueError, match="overlap"):
        fine_tuning.validate_holdout([{"fingerprint": "same"}], [{"fingerprint": "same"}])


def test_binary_metrics():
    assert fine_tuning.binary_metrics([1, 0, 1], [1, 0, 0])["accuracy"] == 2 / 3
