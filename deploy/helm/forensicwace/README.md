# forensicwace Helm chart

Deploys the full platform on Kubernetes: stateless API (FastAPI, HPA on CPU),
Celery analysis workers (KEDA autoscaling on RabbitMQ queue depth), React
frontend, and optional in-cluster PostgreSQL, RabbitMQ and MinIO (the object
storage backing browser uploads from the Projects page).

## Prerequisites

- Kubernetes 1.25+ (tested against stock k3s)
- Images published to a registry (see `image.registry`); build them with:
  ```bash
  docker build -f services/api/Dockerfile    -t <registry>/forensicwace-api:2.0.0a1 .
  docker build -f services/worker/Dockerfile -t <registry>/forensicwace-worker:2.0.0a1 .
  docker build -f frontend/Dockerfile        -t <registry>/forensicwace-frontend:2.0.0a1 .
  ```
- For autoscaling: [KEDA](https://keda.sh/docs/latest/deploy/) installed in the cluster
- For multi-node clusters: a ReadWriteMany StorageClass for the evidence
  volume (NFS, EFS, Longhorn, ...). Backups uploaded through the Projects
  page live durably in object storage (in-cluster MinIO by default, or an
  external S3 via `minio.externalEndpoint`); the evidence volume holds
  their hydrated working copies

## Install

```bash
helm install forensicwace deploy/helm/forensicwace \
  --namespace forensicwace --create-namespace \
  --set image.registry=<your-registry> \
  --set worker.keda.enabled=true
```

Then follow the printed NOTES: port-forward (or enable the ingress), copy the
evidence extractions into the evidence PVC, and open the web UI.

## Autoscaling behaviour

- `api`: HorizontalPodAutoscaler on CPU (`api.hpa.*`).
- `worker`: KEDA `ScaledObject` on the depth of the `media` and `text` queues
  (target `worker.keda.queueLength` messages per replica) plus the `control`
  queue. Submitting a large analysis fans out one task per message, the queues
  fill up, and workers scale from `minReplicas` toward `maxReplicas`; when the
  queues drain, KEDA scales back down after `cooldownPeriod` seconds.

Load-test it: submit an analysis over a large chat and watch
`kubectl get scaledobject,hpa,pods -w`.

## Key values

| Value | Default | Notes |
|---|---|---|
| `image.registry` | `ghcr.io/forensic-wace` | Registry hosting the three images |
| `worker.keda.enabled` | `false` | Requires KEDA installed |
| `worker.keda.queueLength` | `20` | Target msgs per replica |
| `evidence.existingClaim` | `""` | Bring your own PVC |
| `evidence.accessModes` | `[ReadWriteMany]` | RWO works on single-node clusters |
| `postgresql.enabled` | `true` | Lab-grade single node; use `externalUrl` in production |
| `rabbitmq.enabled` | `true` | Same |
| `minio.enabled` | `true` | Same — use `minio.externalEndpoint` + keys for managed S3; disable both to turn off browser uploads |
| `minio.bucket` | `forensicwace-evidence` | Created automatically on first use |
| `analyzerSecrets` | `{}` | FW_* credentials (Secret) |
| `extraEnv` | `{}` | FW_* plain env (endpoints, toggles) |
| `ingress.enabled` | `false` | Frontend ingress |

## Security notes

Authentication is not enforced by the application yet: keep the ingress
disabled or protected (network policy, oauth2-proxy, VPN) on any shared
cluster. Default in-cluster credentials MUST be overridden.
