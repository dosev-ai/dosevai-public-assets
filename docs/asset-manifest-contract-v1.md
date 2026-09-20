# Governed asset manifest contract v1

This repository uses one deterministic packager entry point for asset manifests. The executable profile registry supports `image`, `document_pdf`, `audio`, and `presentation_pptx`; every profile extends the same normalized core instead of creating an independent generator.

## Core fields

`schema_version`, `profile`, `asset_id`, `content_id`, `source_class`, `project`, `source_repository`, `source_path`, `mime_type`, `sha256`, `role`, `alt`, `caption`, `semantic_description`, `claims`, `boundaries`, `creation_method`, `contributor`, `license`, `public_safe`, `guide_eligible`, `external_resources`, and `scripts`.

The image profile retains `visual_id` as a compatibility field and requires it to equal `asset_id`. It also requires `remote_fonts: false`.

Document-like profiles are **owner-attested metadata envelopes**, not machine-certified documents. The packager may reuse the existing evidence fields `source_format`, `render_inspected`, `render_evidence`, and `private_notes_removed`, but those values are explicit owner attestations. The packager must not open, parse, render, inspect, or certify PDF/PPTX internals in order to prove them.

For document profiles the machine-owned boundary is limited to package identity and integrity: manifest schema, exact repository/path adjacency, declared profile/MIME/extension consistency, SHA-256 of the file bytes, deterministic serialization, and presence/type of required owner-supplied fields. Semantic correctness, page/slide review, notes, active/embedded content, accessibility, visual fidelity, private-content removal, and publication suitability remain the owner's responsibility.

The PDF profile retains `page_count`, `embedded_object_policy`, and `annotation_policy` as owner-supplied attestations and uses the shared document evidence fields above. Optional lifecycle fields include `subtitle`, `filename_policy`, and `update_policy`. The repository validator must not parse PDF contents as part of package acceptance.

## Typed profiles

The definitions below are executable profile contracts. `audio` adds bounded byte/source validation appropriate to generated audio. `presentation_pptx` remains an owner-attested document envelope: profile support does not authorize OOXML parsing or document certification.

### Audio profile

The `audio` profile extends the core with:

- `duration_ms`: positive integer producer-supplied observation of the produced asset; v1 validates type/range but does not independently recompute duration;
- `codec`: exactly `mp3` in v1;
- `container`: exactly `mp3` in v1;
- `source_projection_contract`: stable identifier for the algorithm that derives narratable source text, initially `dosevai-narration-v1`;
- `source_projection_path`: repository-relative path to an adjacent audit sidecar containing the exact canonical narration projection used for generation;
- `source_content_hash`: lowercase 64-character SHA-256 recomputed from the exact sidecar bytes;
- `coverage_mode`: bounded enum describing what is voiced, initially `prose_only` or `full_text`;
- `provider_profile`: stable governed provider-profile identifier/version;
- `provider`: explicit provider identity;
- `provider_route`: explicit provider route identity;
- `model`: explicit model identity;
- `voice`: explicit voice identity;
- `instructions`: the exact canonical instruction string dispatched to the provider; empty string means none;
- `assembly_plan_hash`: producer-supplied `sha256:<lowercase-hex>` evidence for the generation/chunk assembly plan;
- `rights_policy`: stable rights-policy identifier/version;
- `safety_policy`: stable safety-policy identifier/version;
- `audio_generation_identity`: deterministic generation-recipe identity defined below;
- `disclosure`: public provenance/coverage disclosure shown with the asset;
- `production_date`: ISO `YYYY-MM-DD` production date.

The common manifest `sha256` is the actual audio **content identity**: it must equal the SHA-256 of the exact output bytes. `audio_generation_identity` identifies the governed generation recipe and must never be described as a content-addressed identity.

#### Initial MP3 envelope

The initial audio profile has one accepted byte envelope:

- source path extension: `.mp3`;
- `mime_type: audio/mpeg`;
- `codec: mp3`;
- `container: mp3`;
- common manifest `sha256`: mandatory lowercase SHA-256 of the exact MP3 bytes.

Aliases such as `audio/mp3`, alternate extensions, or another codec/container pair are unsupported until a reviewed profile change explicitly adds them. An active validator must prove that the exact bytes are decodable MP3; it does not infer the envelope from a filename alone.

#### Recomputable source binding

`dosevai-narration-v1` is normatively bound to `canonicalNarrationProjection` in
`deldos/dosevai-com@8161f49c5f4a50ce1043f0fcb319d813c4fd01d0:src/lib/content/narration.ts`.
That exact commit/path/function defines the markdown selection, structural exclusions, whitespace handling,
inline-markup handling, word bounds, and typography normalization for this contract. A later implementation
change does not alter `dosevai-narration-v1`; changing projection semantics requires a new
`source_projection_contract` identifier and reviewed compatibility/migration decision.

For `dosevai-narration-v1`, the source-projection sidecar bytes are exactly
`UTF8(canonicalNarrationProjection(body).text)`: UTF-8, no BOM, and no LF or CR bytes anywhere.
The pinned projection collapses every whitespace run to U+0020 SPACE before returning `text`; the
packager must not add any further normalization after that versioned projection function has applied its
deterministic markdown, whitespace, and typography rules. The package audit must read `source_projection_path` from the
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

#### Canonical provider instructions

Before provider dispatch, the producer must canonicalize the instruction string through
`audio-instructions-v1`:

1. normalize the complete input string to Unicode NFC;
2. remove the maximal leading run and maximal trailing run containing **only** these code points:
   U+0009 TAB, U+000A LF, U+000B VT, U+000C FF, U+000D CR, and U+0020 SPACE;
3. preserve every other code point and all internal characters exactly.

No other Unicode whitespace, separator, BOM, or format character is trimmed in v1. In particular,
U+0085, U+00A0, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F, U+3000, and U+FEFF are preserved when
they occur at the boundaries. Implementations must apply this code-point rule directly rather than
delegating to a language-default `trim`/`strip` function whose whitespace set may differ.

The resulting canonical string is both:

1. the exact `instructions` value stored in the manifest; and
2. the exact string dispatched to the provider.

The governed path must not dispatch a non-canonical raw variant while hashing or storing the canonical
variant. If provider-visible instructions differ, the manifest value and generation identity must differ.

#### Deterministic audio generation identity

`audio_generation_identity` is:

```text
"sha256:" + lowercase_hex(
  SHA256(
    UTF8(
      JSON.stringify([
        "audio-generation-identity-v1",
        content_id,
        source_content_hash,
        source_projection_contract,
        coverage_mode,
        provider_profile,
        provider,
        provider_route,
        model,
        voice,
        instructions,
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
to NFC before serialization. No locale-aware case folding is applied.

Changing any listed material generation input must change `audio_generation_identity`. The output bytes
do not participate in this recipe identity; the common manifest `sha256` is the separate exact content
identity and distinguishes nondeterministic provider/encoder outputs produced from the same recipe.

`assembly_plan_hash` is explicit producer evidence. In v1 the packager validates only that it has the
required `sha256:<lowercase-hex>` shape; it does not claim to reconstruct or certify the producer's
private chunk/assembly representation. A future profile that needs independent assembly-plan verification
must introduce a reviewed versioned canonicalization contract rather than silently changing v1 semantics.

`duration_ms` is likewise producer evidence in v1. The packager validates it as a positive integer but
does not independently recompute duration because decoder delay/padding and VBR timing rules are not part
of this contract. A future profile may add a versioned duration-measurement rule; until then, byte identity
comes from `sha256`, not from duration equality.

Active audio-package validation requires decodable MP3 bytes, the exact v1 extension/MIME/codec/container mapping, exact
byte-level `sha256`, a recomputable source-content binding, deterministic
`audio_generation_identity` recomputation from declared fields, explicit coverage/provenance fields,
positive and malformed-byte fixtures, repository audit coverage, changed-package CI, and exact-head
independent review. Activation does **not** require the packager to independently derive `duration_ms`
or reconstruct the private assembly plan.

The packager must not infer provider, provider route/profile, licence, disclosure, coverage mode,
instructions, assembly plan, rights/safety policy, or `audio_generation_identity` from model names,
filenames, prose, or URLs.

#### Legacy narration mapping

A legacy narration row may map deterministically as follows:

- `slug` -> `content_id`;
- `source_hash` -> `source_content_hash`;
- `model`, `voice`, `disclosure` -> same semantic fields;
- `generated_at` -> `production_date` only through the deterministic date rule below;
- `format: mp3` -> `codec: mp3` and `container: mp3` only when the asset path ends in `.mp3`, `mime_type` is `audio/mpeg`, and the validator proves the exact bytes are decodable MP3;
- `duration_seconds` -> `duration_ms` only when the conversion is exact at millisecond precision; the mapped value remains producer evidence rather than an independently recomputed validator result.

Legacy production-date normalization is fail-closed. An exact `YYYY-MM-DD` value is accepted unchanged.
An RFC 3339 timestamp is accepted only when it carries an explicit `Z` or numeric UTC offset; normalize
that instant to UTC and emit its UTC calendar date as `YYYY-MM-DD`. A timestamp with no timezone, an
invalid calendar value, or any other ambiguous/non-standard representation is rejected rather than
truncated or guessed.

Legacy `url` is not accepted as provenance. Migration must regenerate the adjacent source-projection
sidecar and verify it against the legacy `source_hash`. `source_repository`, `source_path`,
`provider_profile`, `provider`, `provider_route`, `license`, `coverage_mode`, canonical
provider-dispatched `instructions`, `assembly_plan_hash`, `rights_policy`, `safety_policy`, and the
inputs needed to recompute `audio_generation_identity` require explicit governed values when absent.
Missing semantic authority fails closed rather than being reconstructed from disclosure text.

### Presentation PPTX profile

The `presentation_pptx` profile extends the core with owner-supplied evidence. Its package envelope requires the `.pptx` extension and `application/vnd.openxmlformats-officedocument.presentationml.presentation` MIME type; other extensions or MIME aliases are unsupported unless a reviewed profile change adds them.


- `slide_count`: positive integer attested by the owner;
- `template_contract`: explicit template/brand contract identifier supplied by the owner/producer;
- `speaker_notes_policy`: explicit owner decision; v1 accepts only `forbid` or `reviewed_public`;
- shared `source_format`, `render_inspected`, `render_evidence`, and `private_notes_removed` owner-attestation fields;
- optional `derived_pdf_manifest_path`, `derived_pdf_asset_id`, and `derived_pdf_sha256`; all three must be present together or all absent.

The packager does **not** unzip or parse OOXML, count slides, inspect notes, macros, ActiveX/OLE, relationships, embedded objects, fonts, comments, hyperlinks, media, or other presentation internals. Those checks belong to the owner/reviewer using the appropriate PowerPoint/document workflow before the manifest is approved.

When a derived PDF is declared, the packager may verify only package-level referential integrity: `derived_pdf_manifest_path` resolves to exactly one repository package, its manifest declares `profile: document_pdf`, its `asset_id` equals `derived_pdf_asset_id`, and its declared/actual file SHA-256 equals `derived_pdf_sha256`. This is identity linkage only; it does not parse or certify the PDF.

Active PPTX-package validation requires schema support, deterministic manifest generation/inspection, exact file identity/checksum binding, required owner attestations, package-level positive/negative metadata tests, changed-package CI, and exact-head independent review. It does **not** require malformed-PPTX structural fixtures or a PPTX structural validator.

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

# Normalize a legacy PDF manifest. Safety/render values are explicit owner attestations.
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

`validate`, `normalize`, and `generate` require the real asset bytes for identity/checksum binding. `inspect` is metadata-only. For document profiles, none of these commands constitutes substantive document review or owner approval.

`audit` discovers assets and adjacent manifests under `posts/`, `social/`, `diagrams`, and `shared` by default. It validates actual bytes, full repository-relative source paths, optional expected repository identity, SHA-256 evidence, symlink safety, and deterministic package pairing. Results use these classifications: `pass`, `repair`, `missing_manifest`, `orphan_manifest`, `unsupported_profile`, or `unsafe`.

The command fails when any blocking finding exists. `--allow-status` defers a finding only when its repository-relative manifest is also named by a repeated `--allow-manifest`. Unlisted findings remain blocking, and stale allowlist entries also fail the gate. `--allow-findings` is a non-certifying exploratory mode and must not be used as the steady-state required check after migration.

## PDF owner-attestation boundary

The active owner-attested PDF envelope contract requires a valid manifest schema, exact adjacent repository/path identity, declared MIME/extension consistency, SHA-256 matching the actual file bytes, and required owner-attestation fields with valid scalar types.

The packager does **not** parse PDF structure, count pages, inspect encryption/actions/JavaScript/forms/annotations/attachments/embedded objects, render pages, or determine whether private notes/content were removed. `page_count`, `render_inspected`, `render_evidence`, `private_notes_removed`, `embedded_object_policy`, and `annotation_policy` are owner-supplied evidence. The owner/reviewer is responsible for the substantive document review and for deciding whether the document is public-safe and publication-ready.

Repository package validation must never be described as document certification or owner approval.

## Profile activation and schema evolution

- `schema_version: 1` remains the active schema until an implementation PR changes executable validation.
- The executable supported-profile set remains authoritative; this contract describes the currently supported `image`, `document_pdf`, `audio`, and `presentation_pptx` profiles.
- New profile keys must not appear in production manifests before their package-level schema support and fixtures merge; unknown fields continue to fail closed.
- A profile may extend the core but may not rename or retype a common field.
- Existing names/types reused by another profile retain the same semantics.
- Incompatible field semantics or scalar types require a new schema version and an explicit migration path.
- Legacy mappings are deterministic map-or-reject rules. Missing licence, public-safety, provenance, accessibility, or other semantic authority is never guessed.

## Ownership boundary

Producer/owner workflows create and substantively review the asset and supply explicit semantic metadata and attestations. The packager owns field mapping, serialization, checksums, package identity, repository-wide discovery, and normalized output. For PDF/PPTX it does not own document parsing, content inspection, visual approval, or publication suitability. Publishing skills and application code consume the normalized result and must not reproduce the core field list independently.

## Legacy licence boundary

Legacy prose `rights` cannot be translated automatically into a machine-readable license. Image normalization requires an explicit `--license`; omission fails with `LEGACY_LICENSE_MAPPING_REQUIRED`. PDF normalization may preserve an existing machine-readable licence or accept an explicit override, but it may not infer one from prose. Audio/PPTX producer adapters must likewise supply explicit machine-readable licence authority; the generic CLI does not infer it from legacy prose.
