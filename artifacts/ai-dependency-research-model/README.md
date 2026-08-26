# AI Dependency Research Model

A dated, inspectable Excel research model supporting the article **The AI Bubble Is Only One Risk**.

The workbook maps directional dependencies across AI pricing, serviceable capacity, infrastructure, provider strategy, enterprise adoption, labour, credit, regulation, and geopolitics. It is designed to make the assumptions behind the narrative visible and refreshable rather than leaving them only in prose.

## How to read it

- Start with `README` inside the workbook, then `.Rules`.
- In `Interaction Matrix`, the **row is the driver** and the **column is the target**.
- A populated X/Y cell records a qualitative direction and strength:
  - `+1` to `+5`: the row tends to increase the target;
  - `-1` to `-5`: the row tends to decrease the target;
  - `±1` to `±5`: the relationship is materially conditional or mixed.
- Darker heat indicates a stronger qualitative relationship in the model.
- `Relationships` is the authoritative directional ledger. The matrix is a generated visual projection of that ledger.

## What the scores do not mean

The relationship strengths are **not** probabilities, percentage changes, correlations, investment scores, or composite systemic-risk measures. A blank cell means the relationship is not established in the current model; it does not mean zero impact.

## Scope and evidence boundary

This is a supporting research artifact, not a forecast, investment recommendation, legal assessment, audit framework, or complete enterprise AI-governance model.

The public workbook contains generic/public research logic only. A user may combine the model with their own authorized private context in an AI assistant or enterprise Copilot, but private evidence remains outside this public artifact. If connected-source evidence is not found, that should be treated as **Unknown / not evidenced**, not automatically as proof that a control, policy, or practice is absent.

## Version

- Public version: `0.2`
- Evidence cutoff: `2026-08-24`
- Public release: `2026-08-26`
- Workbook SHA-256: `694d5b037dbcc997ea0635d58235d66fc36f2f2bccc1f2f7a35f790380f30645`

Released version folders are immutable. A material research/model change creates a new version rather than silently rewriting this snapshot.

The analysis is intended to be refreshed at the end of September 2026 so the August relationships can be compared with subsequent pricing, entitlement, provider-positioning, capacity, and market evidence.

## Excel note

This release intentionally preserves the governed workbook's formulas, metadata/control surfaces and native Excel behavior. It therefore does not conform to the repository's default formula-free public-workbook profile. Publication of this specific artifact was explicitly owner-authorized as an administrative exception; that exception does not change the repository-wide default validator. Native cached-value recalculation is not claimed; open the file in Excel and allow calculation before relying on generated formula surfaces.

## License

Released under the repository's **CC0 1.0 Universal** license.
