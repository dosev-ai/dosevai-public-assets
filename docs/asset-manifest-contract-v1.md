# Governed asset manifest contract v1

This repository uses one deterministic packager entry point for asset manifests. The active profiles are `image` and `document_pdf`. The designed but inactive profiles are `audio` and `presentation_pptx`; they must extend the same normalized core instead of creating independent generators.

## Core fields

`schema_version`, `profile`, `asset_id`, `content_id`, `source_class`, `project`, `source_repository`, `source_path`, `mime_type`, `sha256`, `role`, `alt`, `caption`, `semantic_description`, `claims`, `boundaries`, `creation_method`, `contributor`, `license`, `public_safe`, `guide_eligible`, `external_resources`, and `scripts`.

The image profile retains `visual_id` as a compatibility field and requires it to equal `asset_id`. It also requires `remote_fonts: false`.

Document-like profiles may reuse the existing evidence fields `source_format`, `render_inspected`, `render_evidence`, and `private_notes_removed` without changing their names or scalar types. Reuse does not activate an inactive profile; the repository validator remains authoritative for the supported-profile set.

The PDF profile adds `page_count`, `embedded_object_policy`, and `annotation_policy`, and requires the shared document evidence fields above. Optional lifecycle fields include `subtitle`, `filename_policy`, and `update_policy`.

## Designed inactive profiles

The definitions below are design contracts only. They are not accepted package shapes until the repository-local validator, fixtures, changed-package CI, and exact-head independent review activate them.

### Audio profile

The `audio` profile extends the core with:

- `duration_ms`: positive integer measured from decoded audio;
- `codec`: normalized codec identifier; initial implementation may support only `mp3`;
- `container`: normalized container identifier; initial implementation may support only `mp3`;
- `source_content_hash`: lowercase 64-character SHA-256 of the exact governed source projection used for generation;
- `coverage_mode`: bounded enum describing what is voiced, initially `prose_only` or `full_text`;
- `provider`: explicit provider identity;
- `model`: explicit model identity;
- `voice`: explicit voice identity;
- `audio_identity`: content-addressed identity for the governed generation inputs;
- `disclosure`: public provenance/coverage disclosure shown with the asset;
- `production_date`: ISO `YYYY-MM-DD` production date.

Activation requires real-byte decoding, measured duration, MIME/path/checksum binding, source-content-hash binding, explicit coverage/provenance fields, positive and malformed fixtures, repository audit coverage, changed-package CI, and exact-head independent review.

The packager must not infer provider, licence, disclosure, coverage mode, or `audio_identity` from model names, filenames, prose, or URLs.

#### Legacy narration mapping

A legacy narration row may map deterministically as follows:

- `slug` -> `content_id`;
- `source_hash` -> `source_content_hash`;
- `model`, `voice`, `disclosure` -> same semantic fields;
- `generated_at` -> `production_date`;
- `format: mp3` -> initial `codec/container` pair only when the validator proves the bytes are decodable MP3;
- `duration_seconds` -> `duration_ms` only when the conversion is exact at millisecond precision.

Legacy `url` is not accepted as provenance. `source_repository`, `source_path`, `provider`, `license`, `coverage_mode`, and `audio_identity` require explicit governed inputs when absent. Missing semantic authority fails closed rather than being reconstructed from disclosure text.

### Presentation PPTX profile

The `presentation_pptx` profile extends the core with:

- `slide_count`: positive integer measured from the OOXML package;
- `template_contract`: explicit template/brand contract identifier supplied by the producer;
- `speaker_notes_policy`: bounded policy; initial public profile is `forbid`;
- shared `source_format`, `render_inspected`, `render_evidence`, and `private_notes_removed` evidence fields;
- optional `derived_pdf_asset_id` and `derived_pdf_sha256`, which must appear together and bind an explicitly governed PDF derivative.

Activation requires ZIP/OOXML package-integrity validation, exact slide count, rejection of macros/ActiveX/OLE/external relationships and other prohibited active content, enforcement of the speaker-notes policy, render/contact-sheet evidence, MIME/path/checksum binding, positive and malformed fixtures, repository audit coverage, changed-package CI, and exact-head independent review.

The initial public profile must fail when speaker notes are present. A later policy that permits reviewed public notes requires a separately reviewed contract change; it must not be introduced as an implementation shortcut.

A private source PPTX used only to produce a public PDF is not automatically a public `presentation_pptx` package. Do not import, expose, or normalize a private source deck merely because a derived PDF is public.

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

## Profile activation and schema evolution

- `schema_version: 1` remains the active schema until an implementation PR changes executable validation.
- The executable supported-profile set remains authoritative. Design text alone never makes `audio` or `presentation_pptx` valid.
- New profile keys must not appear in production manifests before their validator and fixtures merge; unknown fields continue to fail closed.
- A profile may extend the core but may not rename or retype a common field.
- Existing names/types reused by another profile retain the same semantics.
- Incompatible field semantics or scalar types require a new schema version and an explicit migration path.
- Legacy mappings are deterministic map-or-reject rules. Missing licence, public-safety, provenance, accessibility, or other semantic authority is never guessed.

## Ownership boundary

Producer skills create the asset and supply explicit semantic metadata. The packager owns field mapping, serialization, checksums, structural validation, repository-wide discovery, and normalized output. Publishing skills and application code consume the normalized result and must not reproduce the core field list independently.

## Legacy licence boundary

Legacy prose `rights` cannot be translated automatically into a machine-readable license. Image normalization requires an explicit `--license`; omission fails with `LEGACY_LICENSE_MAPPING_REQUIRED`. PDF normalization may preserve an existing machine-readable licence or accept an explicit override, but it may not infer one from prose. The same rule applies to future audio and PPTX normalization.
