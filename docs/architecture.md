# LoRA ticket classifier architecture

## Request and model path

Train/validation JSONL → strict text/label and overlap checks → DistilBERT LoRA training → validation history → adapter/tokenizer export → classification API

## Boundaries

- **Input:** Separate JSONL files with string text and integer 0/1 labels. Duplicates within a split and overlap across splits are rejected.
- **Runtime:** `ADAPTER_PATH` supplies a reviewed adapter. `BASE_MODEL_ID` must match the approved base model used for training.
- **Failure behavior:** Missing or incompatible adapters make readiness and classification return 503. Model loading may download weights unless pre-cached.

The FastAPI process exposes `/health/live` for process liveness and `/health/ready` for local prerequisites. Each HTTP response carries a generated `X-Request-ID`, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`. JSON request logs record method, path, status, request ID, and duration, never request bodies, query strings, credentials, or user data. Logs are local process telemetry, not a claim of production monitoring.

The [single Helm chart](../k8s/helm/lora-ticket-classifier/) provides rolling updates, probes, resource bounds, security contexts, optional HPA and NetworkPolicy, and a PDB. [Argo CD](../k8s/argocd/application.yaml) points to that chart. Values need environment review before deployment, especially image pull access, ingress peers, external inference egress, and artifact mounts.

## Limits

No private tickets, training result, calibration, monitored rollout, or live routing accuracy is claimed.
