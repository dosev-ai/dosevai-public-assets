# Governed asset manifest contract v1

This repository uses one deterministic packager entry point for asset manifests. The active profiles are `image` and `document_pdf`; audio and PPTX must extend the same normalized core instead of creating independent generators.

## Core fields

`schema_version`, `profile`, `asset_id`, `content_id`, `source_class`, `project`, `source_repository`, `source_path`, `mime_type`, `sha256`, `role`, `alt`, `caption`, `semantic_description`, `claims`, `boundaries`, `creation_method`, `contributor`, `license`, `public_safe`, `guide_eligible`, `external_resources`, and `scripts`.

The image profile retains `visual_id` as a compatibility field and requires it to equal `asset_id`. It also requires `remote_fonts: false`.

The PDF profile adds `page_count`, `source_format`, `render_inspected`, `render_evidence`, `private_notes_removed`, `embedded_object_policy`, and `annotation_policy`. Optional lifecycle fields include `subtitle`, `filename_policy`, and `update_policy`.

## Commands

```bash
# Normalize a legacy image manifest.
python scripts/asset_manifest.py normalize legacy.manifest.yaml \
  --output repaired.manifest.yaml \
  --project personal-operating-system \
  --contributor "OpenAI ChatGPT with Delyan Dosev direction" \
  --license CC0-1.0 \
  --asset figure.svg

# Normalize a legacy PDF manifest. Safety and render evidence are explicit.
python scripts/asset_manifest.py normalize legacy-pdf.manifest.yaml \
  --profile document_pdf \
  --output companion.manifest.yaml \
  --project personal-operating-system \
  --contributor "Delyan Dosev" \
  --content-id post:example \
  --source-repository dosev-ai/dosevai-public-assets \
  --source-path posts/example/companion.pdf \
  --render-inspected \
  --private-notes-removed \
  --render-evidence "Rendered with pdfium and visually inspected" \
  --asset companion.pdf

python scripts/asset_manifest.py validate companion.manifest.yaml --asset companion.pdf
python scripts/asset_manifest.py inspect companion.manifest.yaml
python scripts/asset_manifest.py generate metadata.yaml --output companion.manifest.yaml --asset companion.pdf

# Audit production packages and bind provenance to this canonical repository.
python scripts/asset_manifest.py audit \
  --root . \
  --expected-repository dosev-ai/dosevai-public-assets \
  --format json \
  --output asset-audit.json

# During a bounded migration, defer only one exact known manifest and status.
python scripts/asset_manifest.py audit \
  --root . \
  --expected-repository dosev-ai/dosevai-public-assets \
  --allow-status unsupported_profile \
  --allow-manifest posts/example/companion.manifest.yaml \
  --format text

# Exploratory inventory only. This reports all findings without certifying the tree.
python scripts/asset_manifest.py audit --root . --format text --allow-findings
```

`validate`, `normalize`, and `generate` require the real asset bytes. `inspect` is metadata-only and does not certify a package.

`audit` discovers assets and adjacent manifests under `posts/`, `social/`, `diagrams`, and `shared` by default. It validates actual bytes, full repository-relative source paths, optional expected repository identity, SHA-256 evidence, symlink safety, and deterministic package pairing. Results use these classifications: `pass`, `repair`, `missing_manifest`, `orphan_manifest`, `unsupported_profile`, or `unsafe`.

The command fails when any blocking finding exists. `--allow-status` defers a finding only when its repository-relative manifest is also named by a repeated `--allow-manifest`. Unlisted findings remain blocking, and stale allowlist entries also fail the gate. `--allow-findings` is a non-certifying exploratory mode and must not be used as the steady-state required check after migration.

## PDF certification

A PDF package passes only when all of the following are true:

- the file has a PDF signature and EOF marker and parses structurally in strict mode;
- the actual page count equals the manifest page count;
- the document is not encrypted;
- catalog and page actions, JavaScript, AcroForms, annotations, attachments, associated files, and embedded files are absent;
- render inspection and private-note removal are explicitly asserted;
- embedded-object and annotation policies are both `forbid`;
- MIME, source path, repository identity, and checksum match the actual file.

Render inspection is an evidence gate separate from structural parsing. The packager records the evidence statement but does not fabricate or infer it.

## Ownership boundary

Producer skills create the asset and supply explicit semantic metadata. The packager owns field mapping, serialization, checksums, structural validation, repository-wide discovery, and normalized output. Publishing skills and application code consume the normalized result and must not reproduce the core field list independently.

## Legacy licence boundary

Legacy prose `rights` cannot be translated automatically into a machine-readable license. Image normalization requires an explicit `--license`; omission fails with `LEGACY_LICENSE_MAPPING_REQUIRED`. PDF normalization may preserve an existing machine-readable licence or accept an explicit override, but it may not infer one from prose.
