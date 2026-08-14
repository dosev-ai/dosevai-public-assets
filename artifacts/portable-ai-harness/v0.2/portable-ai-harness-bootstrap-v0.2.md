# Portable AI Harness — Bootstrap Contract v0.2

## Purpose

Use a familiar portable container to explore, test and improve AI-assisted work before deciding whether a richer agent framework, automation platform, custom build, or professional implementation is justified.

The container stores current context, skills, agent profiles, workflows, sources, user stories, synthetic test cases and runs, action history, semantic versions, reflections, approved changes, and retired history. The LLM or AI client is the runtime.

## Bootstrap instruction

Read `_MCP_META` first, then `README`. If onboarding is not complete, run Quick or Guided setup.

1. `ACTIVE` is current approved context; `RETIRED` is historical only.
2. `SKILLS` contains reusable procedures.
3. `AGENTS` contains declarative role profiles that compose named skills.
4. `WORKFLOWS` defines allowed sequences.
5. `USER_STORIES` turns proposed behavior into actors, value, scope, non-goals and testable acceptance criteria.
6. `TEST_CASES` defines bounded synthetic tests. Default to about 10 smoke cases; expand toward 20 when complexity/risk justifies it.
7. `TEST_RUNS` records actual test evidence using Pass / Fail / Blocked / Error. Never mark an unexecuted test Pass.
8. `ACTION_LOG` records material operations and decisions. It does not itself prove approval.
9. `VERSION_LOG` identifies material harness baselines and rollback lineage. Routine runs do not automatically create a new version.
10. `SOURCES` is the evidence registry when present.
11. `REFLECTIONS` contains observations and proposed learning, not automatically approved truth.
12. `CHANGELOG` records approved/applied design or contract changes.
13. Do not infer missing facts. `Unknown` is valid.
14. Do not silently modify current context, skills, agents, workflows, metadata or test expectations.
15. For a material behavior change use: `propose -> user stories/acceptance -> synthetic tests -> challenge -> human approval -> apply -> action log/change log -> version baseline`.

## Core skills

Research; Decide; Plan & Track; Challenge; Synthesize & Record; Reflect & Improve; Define User Stories; Design Synthetic Tests; Execute & Record Tests; Version & Trace.

## Core agent profiles

Coordinator; Hunter; Skeptic; Referee; Reflector; Recorder; Story Designer; Test Designer & Evaluator.

These are profiles interpreted by the available LLM/client. The XLSX itself does not spawn autonomous agents.

## Segregation of duties

- Story Designer defines requirements; it does not approve them.
- Tester derives and executes evaluations; it cannot approve the change it tests.
- Referee adjudicates evidence but does not replace required user approval.
- Recorder writes approved state and preserves lineage; it does not upgrade evidence state by inference.

## Reflection + validation loop

`run -> observe -> reflect -> propose improvement -> define user story -> generate tests -> execute tests -> Skeptic -> Referee -> human approve/reject -> apply -> log action/change -> create new version when material`

Observed behavior is not automatically a personal fact. Synthetic tests are useful evidence but do not prove production safety, business value or external-system correctness.

## Beginner path

1. Pick one recurring task.
2. Use Quick setup.
3. Run one workflow.
4. Reflect.
5. If you propose a material improvement, create a small story/test pack.
6. Keep, repair, discard, or version the harness.
7. Add richer architecture only when the current container stops being enough.
