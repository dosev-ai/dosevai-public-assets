# dosevai-public-assets

Public-safe assets and downloadable working artifacts for dosevai.com.

This repository contains two governed families:

1. Visual assets: SVG covers, diagrams, social cards, and their semantic manifests.
2. Working artifacts: portable, inspectable files that readers can use with compatible AI assistants to explore a method or workflow.

## Start here

If you are a person, choose the artifact you want from `artifacts/` and read its README before opening or uploading files.

If you are an AI assistant that can read this repository, do not guess how an artifact works from filenames alone. Read the artifact README and its current manifest first. For the Portable AI Harness, start at:

```text
artifacts/portable-ai-harness/README.md
```

The artifact README tells you:

- which version is currently recommended for testing;
- which files are authoritative for onboarding;
- how to guide a new user;
- what may be changed;
- what requires user approval;
- what the artifact does not claim to do.

## Repository boundary

Everything in this repository is deliberately public. Do not add:

- confidential employer, client, supplier, or personal information;
- credentials, secrets, private repository references, or internal governance identifiers;
- screenshots from private systems or proprietary datasets;
- unsupported metrics, outcome claims, or maturity claims;
- executable macros, embedded scripts, active content, or hidden network dependencies in downloadable working artifacts.

Repository acceptance and CMS publication are separate decisions. Adding an artifact here does not publish or approve the associated content entry.

## Visual asset contract

Governed SVG assets must:

- be self-contained and editable;
- include an accessible `<title>` and `<desc>`;
- contain no scripts, event handlers, external images, remote fonts, tracking, or private URLs;
- have an adjacent `.manifest.yaml` file with matching provenance, alt text, caption, semantic description, claims, boundaries, creation method, license, and public-safety state;
- use a new immutable path or commit-pinned URL when historical public evidence must remain reproducible.

## Working artifact contract

Working artifacts must:

- have an artifact-specific README that explains human and AI onboarding;
- preserve released versions under immutable version folders;
- declare the current recommended version in a machine-readable manifest;
- contain no credentials, private IDs, macros, ActiveX, OLE payloads, external workbook links, or silent network connections;
- distinguish the artifact/container from the AI runtime that interprets it;
- state material mutation and approval rules explicitly;
- be validated before release and retain validation evidence where useful.

The current public XLSX profile is intentionally **formula-free and visible-sheet-only**. It treats the workbook as an inspectable declarative container while an external AI assistant performs reasoning and execution. A future artifact that genuinely needs formulas, hidden sheets, macros, add-ins, or other active workbook features requires a separately reviewed typed profile rather than weakening this baseline gate.

A working artifact can be experimental. The README and manifest must say so clearly.

## Structure

```text
posts/<post-slug>/cover.svg
posts/<post-slug>/cover.manifest.yaml
social/
diagrams/
shared/
artifacts/
  <artifact-name>/
    README.md
    manifest.json
    v0.1/
    v0.2/
```

## Stable consumption

For stable public consumption, prefer a commit-pinned URL:

```text
https://cdn.jsdelivr.net/gh/dosev-ai/dosevai-public-assets@<commit-sha>/<artifact-path>
```

The longer-term owned-asset destination is `assets.dosevai.com` under the governed media lifecycle.

## License

Unless a file or manifest states otherwise, repository contents are dedicated to the public domain under [CC0 1.0](LICENSE).
