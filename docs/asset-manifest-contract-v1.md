# Governed asset manifest contract v1

This repository uses one deterministic packager entry point for asset manifests. The first executable profile is `image`; audio, PDF, and PPTX must extend the same normalized core instead of creating independent generators.

## Core fields

`schema_version`, `profile`, `asset_id`, `content_id`, `source_class`, `project`, `source_repository`, `source_path`, `mime_type`, `sha256`, `role`, `alt`, `caption`, `semantic_description`, `claims`, `boundaries`, `creation_method`, `contributor`, `license`, `public_safe`, `guide_eligible`, `external_resources`, `scripts`, and profile-specific safety fields such as `remote_fonts`.

The image profile retains `visual_id` as a compatibility field and requires it to equal `asset_id` in schema v1.

## Commands

```bash
python scripts/asset_manifest.py normalize legacy.manifest.yaml \
  --output repaired.manifest.yaml \
  --project personal-operating-system \
  --contributor "OpenAI ChatGPT with Delyan Dosev direction" \
  --license CC0-1.0 \
  --asset figure.svg

python scripts/asset_manifest.py validate repaired.manifest.yaml --asset figure.svg
python scripts/asset_manifest.py inspect repaired.manifest.yaml
python scripts/asset_manifest.py generate metadata.yaml --output figure.manifest.yaml --asset figure.svg

# Audit every production package under posts/, social/, diagrams/, and shared/.
python scripts/asset_manifest.py audit --root . --format json --output asset-audit.json

# Exploratory inventory only. This preserves findings but does not fail the command.
python scripts/asset_manifest.py audit --root . --format text --allow-findings
```

`validate`, `normalize`, and `generate` require the real asset bytes. `inspect` is metadata-only and does not certify a package.

`audit` discovers supported assets and adjacent manifests, validates actual bytes, and returns deterministic classifications: `pass`, `repair`, `missing_manifest`, `orphan_manifest`, `unsupported_profile`, or `unsafe`. It fails with a non-zero exit code when findings exist unless `--allow-findings` is explicitly supplied for a non-certifying inventory pass.

Normalization is fail-closed. Duplicate YAML keys, unknown fields, unsupported public-safety values, wrong scalar types, unsafe paths, MIME mismatches, checksum mismatches, scripts, external resources, inaccessible SVGs, XInclude, foreign namespaces, animation, and active or foreign SVG content return machine-readable error codes.

## Ownership boundary

Producer skills create the asset and supply explicit semantic metadata. The packager owns field mapping, serialization, checksums, validation, repository-wide discovery, and normalized output. Publishing skills and application code consume the normalized result and must not reproduce the core field list independently.

## Legacy licence boundary

Legacy prose `rights` cannot be translated automatically into a machine-readable license. `normalize` requires an explicit `--license`; omission fails with `LEGACY_LICENSE_MAPPING_REQUIRED`. The caller must verify repository policy and may not infer CC0 or another licence from prose rights.
