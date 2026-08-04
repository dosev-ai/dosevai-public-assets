# Governed asset manifest contract v1

This repository uses one deterministic packager entry point for asset manifests. The first executable profile is `image`; audio, PDF, and PPTX must extend the same normalized core instead of creating independent generators.

## Core fields

`schema_version`, `profile`, `asset_id`, `content_id`, `source_class`, `project`, `source_repository`, `source_path`, `mime_type`, `role`, `alt`, `caption`, `semantic_description`, `claims`, `boundaries`, `creation_method`, `contributor`, `license`, `public_safe`, `guide_eligible`, `external_resources`, and `scripts`.

The image profile retains `visual_id` as a compatibility field and requires it to equal `asset_id` in schema v1.

## Commands

```bash
python scripts/asset_manifest.py normalize legacy.manifest.yaml \
  --output repaired.manifest.yaml \
  --project personal-operating-system \
  --contributor "OpenAI ChatGPT with Delyan Dosev direction"

python scripts/asset_manifest.py validate repaired.manifest.yaml --asset figure.svg
python scripts/asset_manifest.py inspect repaired.manifest.yaml
python scripts/asset_manifest.py generate metadata.yaml --output figure.manifest.yaml --asset figure.svg
```

Normalization is fail-closed. Duplicate YAML keys, unknown fields, unsupported public-safety values, wrong scalar types, unsafe paths, MIME mismatches, checksum mismatches, scripts, external resources, inaccessible SVGs, XInclude, foreign namespaces, animation, and active or foreign SVG content return machine-readable error codes.

## Ownership boundary

Producer skills create the asset and supply explicit semantic metadata. The packager owns field mapping, serialization, checksums, validation, and normalized output. Publishing skills and application code consume the normalized result and must not reproduce the core field list independently.
