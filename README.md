# dosevai-public-assets

Public-safe visual assets for [dosevai.com](https://dosevai.com): versioned SVG covers, diagrams, social cards, and semantic manifests used by the governed CMS publishing workflow.

## Repository boundary

This repository contains deliberately public visual artifacts. Do not add:

- confidential employer, client, supplier, or personal information;
- credentials, secrets, private repository references, or internal governance identifiers;
- screenshots from private systems or proprietary datasets;
- unsupported metrics, outcome claims, or maturity claims.

Repository acceptance and CMS publication are separate decisions. Adding an asset here does not publish or approve the associated content entry.

## Asset contract

Governed SVG assets must:

- be self-contained and editable;
- include an accessible `<title>` and `<desc>`;
- contain no scripts, event handlers, external images, remote fonts, tracking, or private URLs;
- have an adjacent `.manifest.yaml` file with matching provenance, alt text, caption, semantic description, claims, boundaries, creation method, license, and public-safety state;
- use a new immutable path or commit-pinned URL when historical public evidence must remain reproducible.

## Structure

```text
posts/<post-slug>/cover.svg
posts/<post-slug>/cover.manifest.yaml
social/
diagrams/
shared/
```

## Consumption

For stable public consumption, use a commit-pinned CDN URL:

```text
https://cdn.jsdelivr.net/gh/dosev-ai/dosevai-public-assets@<commit-sha>/<asset-path>
```

The longer-term owned-asset destination is `assets.dosevai.com` under the governed media lifecycle.

## License

Unless a file or manifest states otherwise, repository contents are dedicated to the public domain under [CC0 1.0](LICENSE).
