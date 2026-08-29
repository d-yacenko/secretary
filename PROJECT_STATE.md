# Project state

## Current phase

PHASE 19 — local files and huge datasets: **review corrective implemented, awaiting review**

PHASE 19.5 — auth + connections: **not started**

PHASE 20 — Flutter client: **not started**

PHASE 18 — resource registration: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–18: (prior phases)
- PHASE 19 corrective:
  - User-scoped device mirrors with filesystem-safe device dirs
  - Shared `local_files_data` volume for api/worker
  - Path-based `external_id`; bounded text/CSV/Parquet ingest and dataset tools
  - Idempotent `ingest_local_file` with revision/policy expectations
  - Trusted path resolution only (no arbitrary `canonical_uri` filesystem access)
  - Honest bounded scan semantics

## Not done

- PHASE 19 review acceptance
- PHASE 19.5+ (auth, Flutter)

## Next phase

PHASE 19.5 after PHASE 19 acceptance.
