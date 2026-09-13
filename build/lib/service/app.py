"""Serve an explicitly configured LoRA adapter for binary ticket routing."""

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="LoRA ticket classifier", version="0.1.0")


class Ticket(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


@lru_cache(maxsize=1)
def bundle():
    model_path = Path(os.getenv("ADAPTER_PATH", "/models/ticket-lora"))
    if not (model_path / "adapter_config.json").is_file():
        raise FileNotFoundError(model_path)
    import torch
    from peft import PeftModel
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_id = os.getenv("BASE_MODEL_ID", "distilbert-base-uncased")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    base = AutoModelForSequenceClassification.from_pretrained(model_id, num_labels=2)
    model = PeftModel.from_pretrained(base, model_path).eval()
    return torch, tokenizer, model


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    try:
        bundle()
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(503, "Adapter unavailable")
    return {"status": "ready"}


@app.post("/classify")
def classify(ticket: Ticket):
    try:
        torch, tokenizer, model = bundle()
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(503, "Adapter unavailable")
    inputs = tokenizer(ticket.text, truncation=True, max_length=256, return_tensors="pt")
    with torch.inference_mode():
        probabilities = torch.softmax(model(**inputs).logits[0], dim=0)
    return {"label": int(probabilities.argmax()), "confidence": float(probabilities.max())}
