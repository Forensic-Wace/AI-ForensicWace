# Analyzer catalog

`catalog.json` is the seed **fw-catalog/1** document served to the marketplace
page (`FW_CATALOG_URL`). Each entry embeds the analyzer's fw-analyzer/1
manifest plus the container image **pinned to a sha256 digest** — the API
rejects entries that reference tags.

> The seed entries wrap the four historical sidecars through
> `services/analyzer-shim` and carry a **placeholder digest**: update it with
> the real one after building/pushing the shim image
> (`docker buildx imagetools inspect <image> --format '{{json .Manifest.Digest}}'`).
> Their `env` points at the compose sidecar hostnames (`analyzers-local`
> profile); adjust for your runtime.

## Signing (production)

The catalog is authenticated with a detached Ed25519 signature published next
to it (`catalog.json.sig`). Deployments pin the public key:

```bash
python tools/sign_catalog.py keygen --out-dir keys/          # once; keep .key offline
python tools/sign_catalog.py sign catalog/catalog.json --key keys/catalog-signing.key
python tools/sign_catalog.py verify catalog/catalog.json --pub keys/catalog-signing.pub

# deployment:
FW_CATALOG_URL=https://example.org/catalog.json
FW_CATALOG_PUBLIC_KEY=$(cat keys/catalog-signing.pub)
```

With `FW_CATALOG_PUBLIC_KEY` set the API **refuses** unsigned or tampered
catalogs. Without it the catalog loads but the marketplace shows it as
*unverified* — acceptable for a lab, not for production.

## Hosting

Simplest: serve the two files from any static host (or keep them in a git
repo and use the raw URL). `file://` paths work for air-gapped labs — the
compose deployment mounts this directory read-only into the API container.
