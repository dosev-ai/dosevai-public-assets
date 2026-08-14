# Portable AI Harness — Cross-Provider Experiment Protocol v0.2

## Objective

Test whether an ordinary user can obtain structured, repeatable value from the same provider-neutral harness without first learning an agent framework, while preserving explicit requirements, synthetic evaluation, action traceability and version lineage.

## Providers

Run on consumer/free tiers where the feature is available at test time: ChatGPT Free, Gemini without a paid Google AI plan, and Claude Free. Record exact date, tier, model/mode and product limits. Do not assume parity.

## Fixed artifacts

- `portable-ai-harness-v0.2.xlsx`
- `portable-ai-harness-bootstrap-v0.2.md`

Do not modify the baseline artifacts between providers during the first comparison run.

## Baseline tests

1. **Bootstrap comprehension** — identify container/runtime boundary, current/history separation, mutation rule and version/action semantics.
2. **XLSX intake** — read metadata first and identify onboarding.
3. **Guided onboarding** — capture goal, sources, actions, approvals, privacy boundary and test depth without inventing facts.
4. **Challenge workflow** — Hunter -> Skeptic -> Referee with explicit adjudication.
5. **Reflection** — propose learning without silently activating it.
6. **Agent composition** — run a named profile using only allowed skills.
7. **User-story generation** — turn a proposed new capability into actor/value/scope/non-goals/Given-When-Then acceptance/evidence.
8. **Synthetic test design** — create a smoke pack of about 10 cases; for an expanded run, create about 20 including edge, negative and regression scenarios.
9. **Test execution evidence** — where runtime supports repeatable execution, record Pass/Fail/Blocked/Error in `TEST_RUNS`; never infer a Pass.
10. **Segregation of duties** — Tester cannot approve the change it evaluates; Referee cannot bypass required human approval.
11. **Version/action trace** — after an approved material change, preserve distinct `ACTION_LOG`, `CHANGELOG` and `VERSION_LOG` records. Routine runs must not automatically create a new baseline.
12. **Fresh-chat continuation** — distinguish current, proposed, historical, latest version and unresolved test failures from the file alone.
13. **Parallel-context exploration** — run two chats from the same baseline with intentionally different context/roles; preserve why outputs differ.
14. **Two-harness synthesis** — provide two compatible harness files and test whether the runtime can synthesize without silently merging incompatible authority/state.

## Result scale

- **Pass** — usable with no material repair.
- **Partial** — useful but needs extra instructions or loses some contract semantics.
- **Fail** — violates a core contract or materially misinterprets state.
- **Blocked** — product/tier lacks the needed file/tool/runtime capability.
- **Error** — execution failed for a technical reason distinct from model behavior.

## Evaluation principle

Provider differences are evidence, not defects. Re-run the same test set after harness changes and compare results by version. Synthetic evaluation supports exploration and regression detection; it does not replace responsible-AI review, real-user evidence or production validation.

## Capability baseline

Use the v0.1 protocol's 2026-08-14 provider capability notes as historical planning context only. Re-check official product documentation and actual free-tier behavior before publication.
