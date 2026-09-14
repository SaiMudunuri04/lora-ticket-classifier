import json

import pytest

from service import fine_tuning


def test_train_validation_overlap_rejected():
    with pytest.raises(ValueError, match="overlap"):
        fine_tuning.validate_holdout([{"fingerprint": "same"}], [{"fingerprint": "same"}])


def test_binary_metrics():
    assert fine_tuning.binary_metrics([1, 0, 1], [1, 0, 0])["accuracy"] == 2 / 3


@pytest.mark.parametrize("text,label", [("Route this", 0.8), ("Route this", True), (None, 1)])
def test_malformed_training_examples_rejected(tmp_path, text, label):
    path = tmp_path / "examples.jsonl"
    rows = [{"text": text, "label": label},
            {"text": "second", "label": 0}, {"text": "third", "label": 1},
            {"text": "fourth", "label": 0}]
    path.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="Invalid record"):
        fine_tuning.load_examples(path)
