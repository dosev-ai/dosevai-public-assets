# Portable AI Harness

A public, provider-neutral starting point for exploring a structured AI workflow without first building an agent platform.

The spreadsheet is the portable control and context container. Your chosen AI assistant is the runtime that reads and uses it.

## If you are an AI assistant, start here

1. Read `manifest.json` and identify `recommended_version` and its status.
2. Read the bootstrap document inside that version folder.
3. If you can read XLSX files, inspect the workbook metadata and README before doing anything else.
4. Ask the user what they want to explore. Offer a small choice:
   - Quick setup
   - Guided setup
   - Research
   - Decide
   - Plan and Track
   - Custom
5. Use only the skills, agent profiles, workflows, sources, and current state that the selected harness authorizes.
6. Treat `ACTIVE` as current context and `RETIRED` as history. Do not silently promote observations into current truth.
7. Reflection may propose an improvement. Material changes to context, skills, agent instructions, workflows, or approval rules require explicit user approval before mutation.
8. Record material executions in `ACTION_LOG`, harness design changes in `CHANGELOG`, evaluation evidence in `TEST_RUNS`, and released baselines in `VERSION_LOG` when those sheets exist in the selected version.
9. If a capability is unavailable in the current AI product, say so and continue with the closest supported path. Do not claim identical behavior across providers.
10. When the user wants to continue later, return an updated workbook or a clear set of changes they can save into their owned version.

A useful first instruction from the user is simply:

```text
Use this repository to help me build a portable AI harness for one recurring activity. Start with the recommended version and guide me.
```

No prompt-engineering tutorial is required before starting.

## If you are a person

### Fastest path

Give this repository or this README to an AI assistant that can read GitHub and ask it to guide you.

If repository access is unavailable, use either:

- the bootstrap Markdown file for the current version; or
- the current XLSX file if your assistant accepts spreadsheets.

### What to expect

The harness can help you externalize:

- current context and state;
- reusable skills and workflows;
- role or agent profiles such as Hunter, Skeptic, Referee, Reflector, and Tester;
- sources and assumptions;
- reflection and proposed improvements;
- user stories and synthetic tests;
- action history, change history, and version lineage.

You do not have to use every module. Start with one recurring activity and ignore the rest until useful.

## Current versions

### v0.1 - baseline

Introduced the provider-neutral workbook, machine-readable onboarding, reusable workflows, role profiles, source registry, reflection, change history, and retired state.

Use v0.1 when you want to see the smaller baseline before testing and version-control features were added.

### v0.2 - current recommended experiment baseline

Adds:

- `USER_STORIES`;
- `TEST_CASES`;
- `TEST_RUNS`;
- `ACTION_LOG`;
- `VERSION_LOG`;
- Story Designer and Test Designer/Evaluator profiles;
- synthetic smoke and expanded-test concepts;
- clearer separation between execution history, design changes, and released versions.

v0.2 is an experimental MVP candidate. Cross-provider free-tier testing is intentionally post-MVP validation and does not block this repository release. Do not describe the harness as universally compatible or production-ready until that evidence exists.

## Folder layout

```text
portable-ai-harness/
  README.md
  manifest.json
  v0.1/
    portable-ai-harness-v0.1.xlsx
    portable-ai-harness-bootstrap-v0.1.md
    portable-ai-harness-experiment-protocol-v0.1.md
    portable-ai-harness-v0.1-scan.json
  v0.2/
    portable-ai-harness-v0.2.xlsx
    portable-ai-harness-bootstrap-v0.2.md
    portable-ai-harness-experiment-protocol-v0.2.md
    portable-ai-harness-v0.2-scan.json
```

## Version policy

- Version folders are immutable after merge.
- Improvements create a new version folder.
- `manifest.json` identifies the current recommended version and hashes the released files.
- A new version is not automatically better for every user; previous versions remain available for comparison and rollback.
- Runtime experiments should record the exact artifact version and provider used.

## Safety and privacy

The v0.1 and v0.2 starter workbooks use the repository's deliberately narrow public XLSX profile:

- standard `.xlsx` only;
- no workbook formulas or defined-name expressions;
- no hidden or very-hidden sheets;
- no macros, ActiveX, OLE, embedded payloads, add-ins, macro sheets, or web-extension/task-pane parts;
- no external workbook relationships or absolute/network relationship targets;
- no credentials or private governance identifiers.

This is intentional. The workbook is the **declarative container**; the AI assistant is the **reasoning/runtime layer**. If a future working artifact genuinely needs formulas or other active Excel features, it should receive a separate typed validation profile instead of broadening this starter profile by default.

That does not make AI usage risk-free. Anything you upload is handled under the terms, privacy controls, retention rules, and organizational policy of the AI service you choose. Do not place confidential or restricted work data into an unapproved service.

## What this is not

This repository does not claim that:

- Excel itself is an autonomous agent runtime;
- several worksheets or workbooks automatically become independent agents;
- the harness replaces enterprise identity, security, observability, or orchestration platforms;
- all providers support the same file, URL, repository, or editing capabilities;
- every experiment should graduate into a more complex system.

The point is simpler: explore the operating pattern in a familiar, inspectable form first. Add architecture only when the work earns it.
