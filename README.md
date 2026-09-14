# LoRA ticket classifier

[Architecture](docs/architecture.md) · [Operations runbook](docs/operations.md) · [Helm chart](k8s/helm/lora-ticket-classifier/) · [Argo CD application](k8s/argocd/application.yaml)

An independent service for parameter-efficient model adaptation. This repository contains executable source, tests,
a container, Helm release, Argo CD application, and a CI workflow that builds an
immutable GHCR image after tests pass. It is a reference implementation; it has not
been deployed to a user's AWS account or Kubernetes cluster.

## Run

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check .
helm lint k8s/helm/lora-ticket-classifier --strict
uvicorn service.app:app --reload
```

`/health/live` checks the process. `/health/ready` checks required local resources. Responses include a request ID and no-store/nosniff headers; JSON request logs omit bodies and query strings.
Configure data, model artifacts, and inference endpoints before serving traffic.

## Delivery

The workflow tests pull requests, then builds/pushes an image to GHCR on `main` and
updates the Helm image tag to the tested commit. Argo CD follows the single chart at [`k8s/helm/lora-ticket-classifier/`](k8s/helm/lora-ticket-classifier/).
Install `k8s/argocd/application.yaml` in a cluster with Argo CD, set environment-specific
Helm values, provide secrets through a cluster secret manager, and make the package
pullable by the cluster. Model/data volumes are configured through `volumes` and
`volumeMounts`; use `envFromSecretName` for credentials. The workflow does not
provision AWS or a cluster.

`.env.example` contains placeholders only. Never commit credentials or private data.

## Train and serve

Provide separate train and validation JSONL files with `text` and binary `label`. Duplicate texts within each file and overlap between splits are rejected. The trainer adapts a DistilBERT classifier with LoRA, evaluates each epoch, and exports the adapter and tokenizer.

```sh
python -m service.fine_tuning /path/train.jsonl /path/validation.jsonl --output artifacts/ticket-lora
ADAPTER_PATH=artifacts/ticket-lora BASE_MODEL_ID=distilbert-base-uncased uvicorn service.app:app --host 127.0.0.1
```

Mount the adapter read-only and pre-cache the approved base model for serving. A domain-specific test set, calibration, and monitored rollout remain necessary before live ticket routing. No fine-tuning run or performance on private tickets is claimed.
