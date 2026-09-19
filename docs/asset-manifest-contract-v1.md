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
- `source_projection_contract`: stable identifier for the algorithm that derives narratable source text, initially `dosevai-narration-v1`;
- `source_projection_path`: repository-relative path to an adjacent audit sidecar containing the exact canonical narration projection used for generation;
- `source_content_hash`: lowercase 64-character SHA-256 recomputed from the exact sidecar bytes;
- `coverage_mode`: bounded enum describing what is voiced, initially `prose_only` or `full_text`;
- `provider_profile`: stable governed provider-profile identifier/version;
- `provider`: explicit provider identity;
- `provider_route`: explicit provider route identity;
- `model`: explicit model identity;
- `voice`: explicit voice identity;
- `instructions`: explicit generation instructions; empty string means none;
- `assembly_plan_hash`: `sha256:<lowercase-hex>` of the canonical chunk/assembly plan;
- `rights_policy`: stable rights-policy identifier/version;
- `safety_policy`: stable safety-policy identifier/version;
- `audio_identity`: deterministic content-addressed identity defined below;
- `disclosure`: public provenance/coverage disclosure shown with the asset;
- `production_date`: ISO `YYYY-MM-DD` production date.

#### Recomputable source binding

For `dosevai-narration-v1`, the source-projection sidecar bytes are exactly
`UTF8(canonicalNarrationProjection(body).text)`: UTF-8, no BOM, no added trailing newline, and no
additional normalization after the projection function has applied its own deterministic markdown,
whitespace, and typography rules. The package audit must read `source_projection_path` from the
repository, require it to be an adjacent regular file inside the same package directory, and require:

```text
source_content_hash = lowercase_hex(SHA256(source_projection_sidecar_bytes))
```

The sidecar is itself public repository material. It may contain only a narration projection already
approved for public exposure; it must never be used to move private, draft-only, embargoed, or otherwise
non-public source text into this repository merely to make the hash recomputable. If the authoritative
source is not yet public-safe, the public audio package remains unavailable and any source evidence stays
in a separately governed private staging surface.

The `source_projection_contract` is versioned semantic authority. Any change to projection rules that
can change canonical output bytes requires a new contract identifier and migration/compatibility review;
an implementation change may not silently reuse `dosevai-narration-v1`.

A migration from the current dosevai.com narration manifest must regenerate this sidecar from the
authoritative article body through the named projection contract and require the resulting digest to
equal the legacy `source_hash`. A legacy `slug` + `source_hash` pair without a recomputable projection
is therefore not sufficient for profile activation. The consumer may additionally recompute the same
projection from the current article body at render/read time and fail closed on drift, matching the
existing dosevai.com narration behavior.

This source binding certifies the exact declared generation source. It does not claim that deterministic
asset validation can independently prove spoken-word equivalence between arbitrary audio and text.

#### Deterministic audio identity

`audio_identity` is:

```text
"sha256:" + lowercase_hex(
  SHA256(
    UTF8(
      JSON.stringify([
        "audio-identity-v1",
        content_id,
        source_content_hash,
        source_projection_contract,
        provider_profile,
        provider,
        provider_route,
        model,
        voice,
        normalized_instructions,
        assembly_plan_hash,
        codec,
        container,
        rights_policy,
        safety_policy
      ])
    )
  )
)
```

The array order above is normative. JSON serialization is compact JSON with standard JSON escaping,
no extra spaces, no BOM, and no trailing newline. Every identifier/value is a Unicode string normalized
to NFC before serialization. `normalized_instructions` is the NFC-normalized `instructions` value
with leading/trailing whitespace removed and internal characters otherwise preserved; absence is the
empty string. No locale-aware case folding is applied. `assembly_plan_hash` is itself a
`sha256:<lowercase-hex>` digest of the implementation's separately canonicalized chunk/assembly plan.

Changing any listed material input must change `audio_identity`. Values not listed above, such as a
request ID or cost ceiling, are request/execution metadata and do not define the produced audio's
content identity.

Activation requires real-byte decoding, measured duration, MIME/path/checksum binding, a recomputable
source-content binding, deterministic audio-identity recomputation, explicit coverage/provenance fields,
positive and malformed fixtures, repository audit coverage, changed-package CI, and exact-head
independent review.

The packager must not infer provider, provider route/profile, licence, disclosure, coverage mode,
instructions, assembly plan, rights/safety policy, or `audio_identity` from model names, filenames,
prose, or URLs.

#### Legacy narration mapping

A legacy narration row may map deterministically as follows:

- `slug` -> `content_id`;
- `source_hash` -> `source_content_hash`;
- `model`, `voice`, `disclosure` -> same semantic fields;
- `generated_at` -> `production_date` only through the deterministic date rule below;
- `format: mp3` -> initial `codec/container` pair only when the validator proves the bytes are decodable MP3;
- `duration_seconds` -> `duration_ms` only when the conversion is exact at millisecond precision.

Legacy production-date normalization is fail-closed. An exact `YYYY-MM-DD` value is accepted unchanged. An RFC 3339 timestamp is accepted only when it carries an explicit `Z` or numeric UTC offset; normalize that instant to UTC and emit its UTC calendar date as `YYYY-MM-DD`. A timestamp with no timezone, an invalid calendar value, or any other ambiguous/non-standard representation is rejected rather than truncated or guessed.

Legacy `url` is not accepted as provenance. Migration must regenerate the adjacent source-projection sidecar and verify it against the legacy `source_hash`. `source_repository`, `source_path`, `provider_profile`, `provider`, `provider_route`, `license`, `coverage_mode`, `instructions`, `assembly_plan_hash`, `rights_policy`, `safety_policy`, and the inputs needed to recompute `audio_identity` require explicit governed values when absent. Missing semantic authority fails closed rather than being reconstructed from disclosure text.

### Presentation PPTX profile

The `presentation_pptx` profile extends the core with:

- `slide_count`: positive integer measured from the OOXML package;
- `template_contract`: explicit template/brand contract identifier supplied by the producer;
- `speaker_notes_policy`: bounded policy; initial public profile is `forbid`;
- shared `source_format`, `render_inspected`, `render_evidence`, and `private_notes_removed` evidence fields;
- optional `derived_pdf_manifest_path`, `derived_pdf_asset_id`, and `derived_pdf_sha256`; all three must be present together or all absent.

#### Normative PPTX v1 package allowlist

The initial public `presentation_pptx` profile is a static text/shapes/tables/raster-image deck. Validation is allowlist-based, not a best-effort blacklist.

Allowed package part classes are limited to:

- `[Content_Types].xml` and `_rels/.rels`;
- optional `docProps/core.xml` and `docProps/app.xml`;
- `ppt/presentation.xml`, `ppt/_rels/presentation.xml.rels`, and optional `ppt/presProps.xml`, `ppt/viewProps.xml`, and `ppt/tableStyles.xml`;
- `ppt/slides/slideN.xml` plus its relationship part;
- `ppt/slideLayouts/slideLayoutN.xml` plus its relationship part;
- `ppt/slideMasters/slideMasterN.xml` plus its relationship part;
- `ppt/theme/themeN.xml`;
- `ppt/media/*` only for decoded PNG or JPEG image bytes whose extension/content type/signature agree.

The main presentation content type must be the ordinary non-macro-enabled PPTX type. Every package relationship must use an explicitly allowed relationship class: office document, core properties, extended properties, slide, slide layout, slide master, theme, image, presentation properties, view properties, or table styles. Every relationship target must be internal, resolve inside the package to an allowed existing part, and use safe normalized package syntax. `TargetMode="External"`, absolute/network targets, parent traversal, backslashes, and unknown relationship types fail closed.

Everything outside that allowlist is rejected in v1. In particular, validation must reject VBA/macro parts, ActiveX/control parts, OLE or embedded/package objects, external links, hyperlinks/actions, custom UI/XML, web extensions/task panes, embedded fonts, audio/video/media other than the allowed raster images, notes slides/notes masters, comments/comment authors/people metadata, and unknown non-XML package members. Slide XML must also reject hyperlink/action elements and embedded/control/media object elements rather than relying only on relationship checks. New legitimate PPTX capabilities require a reviewed profile change before the validator may accept them.

The validator must count the actual `ppt/slides/slideN.xml` parts and require equality with `slide_count`; it must also enforce archive-entry, decompressed-size/compression-ratio, duplicate/case-collision, XML parsing, DTD/entity, private-identifier, and relationship-graph safeguards equivalent in intent to the repository's existing public OOXML workbook validation.

#### Derived PDF referential integrity

When a derived PDF is declared, `derived_pdf_manifest_path` must resolve inside the same repository audit inventory to exactly one currently supported `document_pdf` manifest. That manifest must validate successfully; its `asset_id` must equal `derived_pdf_asset_id`; its manifest `sha256` must equal `derived_pdf_sha256`; and the PDF asset resolved by that manifest must exist and its actual bytes must hash to the same SHA-256. A path outside the repository, an inactive/unsupported profile, an ambiguous/missing manifest, or any ID/hash/byte mismatch fails closed. The PPTX manifest never infers a PDF relationship from filenames or URLs.

Activation requires ZIP/OOXML package-integrity validation, exact slide count, the normative package/relationship allowlist above, enforcement of the speaker-notes policy, render/contact-sheet evidence, MIME/path/checksum binding, derived-PDF referential integrity when declared, positive and malformed fixtures, repository audit coverage, changed-package CI, and exact-head independent review.

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
