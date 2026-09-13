"""LoRA fine-tuning for binary support-ticket routing with held-out evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


def load_examples(path: Path) -> list[dict]:
    examples = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            text = str(record["text"]).strip()
            label = int(record["label"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid record at line {number}") from exc
        if not text or label not in (0, 1):
            raise ValueError(f"Invalid text or binary label at line {number}")
        fingerprint = hashlib.sha256(text.casefold().encode()).hexdigest()
        if fingerprint in seen:
            raise ValueError(f"Duplicate text at line {number}")
        seen.add(fingerprint)
        examples.append({"text": text, "label": label, "fingerprint": fingerprint})
    if len(examples) < 4 or {row["label"] for row in examples} != {0, 1}:
        raise ValueError("Each file needs at least four examples and both labels")
    return examples


def validate_holdout(training: list[dict], validation: list[dict]) -> None:
    overlap = {row["fingerprint"] for row in training} & {row["fingerprint"] for row in validation}
    if overlap:
        raise ValueError("Train/validation text overlap detected")


def binary_metrics(predictions: list[int], labels: list[int]) -> dict:
    if len(predictions) != len(labels) or not labels:
        raise ValueError("Predictions and labels must be nonempty and aligned")
    tp = sum(p == 1 and y == 1 for p, y in zip(predictions, labels))
    fp = sum(p == 1 and y == 0 for p, y in zip(predictions, labels))
    fn = sum(p == 0 and y == 1 for p, y in zip(predictions, labels))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"accuracy": sum(p == y for p, y in zip(predictions, labels)) / len(labels),
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def train(training_path: Path, validation_path: Path, output: Path, *,
          model_id: str = "distilbert-base-uncased", epochs: int = 3,
          batch_size: int = 8, learning_rate: float = 2e-4, seed: int = 42) -> dict:
    if epochs < 1 or batch_size < 1 or learning_rate <= 0:
        raise ValueError("Training parameters must be positive")
    training = load_examples(training_path)
    validation = load_examples(validation_path)
    validate_holdout(training, validation)

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

    random.seed(seed)
    torch.manual_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, num_labels=2)
    config = LoraConfig(task_type=TaskType.SEQ_CLS, r=8, lora_alpha=16, lora_dropout=0.1,
                        target_modules=["q_lin", "v_lin"],
                        modules_to_save=["classifier", "pre_classifier"])
    model = get_peft_model(model, config)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    collator = DataCollatorWithPadding(tokenizer=tokenizer, return_tensors="pt")

    def make_loader(records: list[dict], shuffle: bool) -> DataLoader:
        encoded = [dict(tokenizer(row["text"], truncation=True, max_length=256), labels=row["label"])
                   for row in records]
        return DataLoader(encoded, batch_size=batch_size, shuffle=shuffle, collate_fn=collator)

    train_loader = make_loader(training, True)
    val_loader = make_loader(validation, False)
    optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad),
                                  lr=learning_rate)
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad()
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
        model.eval()
        predictions, labels = [], []
        with torch.inference_mode():
            for batch in val_loader:
                labels.extend(batch["labels"].tolist())
                batch = {key: value.to(device) for key, value in batch.items()}
                predictions.extend(model(**batch).logits.argmax(dim=1).cpu().tolist())
        history.append({"epoch": epoch, **binary_metrics(predictions, labels)})
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output)
    tokenizer.save_pretrained(output)
    report = {"model_id": model_id, "task": "binary_support_ticket_routing",
              "train_examples": len(training), "validation_examples": len(validation),
              "seed": seed, "device": device, "history": history}
    (output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train_jsonl", type=Path)
    parser.add_argument("validation_jsonl", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/ticket-lora"))
    parser.add_argument("--model", default="distilbert-base-uncased")
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(train(args.train_jsonl, args.validation_jsonl, args.output,
                           model_id=args.model, epochs=args.epochs), indent=2))


if __name__ == "__main__":
    main()
