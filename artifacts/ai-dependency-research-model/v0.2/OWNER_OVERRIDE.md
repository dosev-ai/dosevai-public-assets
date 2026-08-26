# Owner-approved public workbook exception

This artifact version intentionally publishes the full governed Excel workbook rather than a formula-free static derivative.

Scope of the exception:

- artifact: `ai-dependency-research-model`
- version: `0.2`
- workbook: `ai-dependency-research-matrix-v0.2.xlsx`
- workbook SHA-256: `694d5b037dbcc997ea0635d58235d66fc36f2f2bccc1f2f7a35f790380f30645`
- decision: owner/admin override for this artifact version only

The workbook has separately passed the governed workbook integrity, metadata, public-safety and X/Y model checks recorded in the adjacent scan. It intentionally retains formulas and governed workbook control surfaces, so the repository's default formula-free public-workbook validator is expected to reject it. That expected rejection is evidence of a scoped policy exception; it is not represented as a passing default-profile validation.

This exception does not weaken or modify the repository-wide validator for other workbook artifacts.
