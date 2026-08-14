# Portable AI Harness — Bootstrap Contract v0.1

## Purpose

Use a familiar portable container to explore and improve AI-assisted work before deciding whether a richer agent framework, automation platform, custom build, or professional implementation is justified.

The container stores context, skills, agent profiles, workflows, sources, reflections, changes, and retired history. The LLM or AI client is the runtime.

## Bootstrap instruction

Read the container metadata first, then the human README. If onboarding is not complete, run Quick or Guided setup.

1. Treat `ACTIVE` as current context and `RETIRED` as history only.
2. Treat `SKILLS` as reusable procedures.
3. Treat `AGENTS` as declarative role profiles that compose named skills.
4. Treat `WORKFLOWS` as the allowed sequence for a task.
5. Treat `SOURCES` as the evidence registry when present.
6. Treat `REFLECTIONS` as observations and proposed learning, not automatically approved truth.
7. Treat `CHANGELOG` as the record of approved/applied changes.
8. Do not infer missing facts. `Unknown` is a valid state.
9. Do not silently change current context, skills, agents, workflows, or metadata.
10. For a material change use: `propose -> challenge -> human approval -> apply -> preserve prior state -> changelog`.

## Core skills

- **Research** — gather, compare and classify evidence; keep fact, interpretation and Unknown separate.
- **Decide** — compare options and trade-offs and issue a bounded recommendation.
- **Plan & Track** — turn a goal into steps, dependencies, gates and next actions.
- **Challenge** — use Hunter, Skeptic and Referee for structured dissent followed by adjudication.
- **Synthesize & Record** — combine outputs without erasing disagreement, provenance, or state.
- **Reflect & Improve** — learn from completed work, propose the smallest reusable improvement, challenge it, and activate it only after approval.

## Core agent profiles

- **Coordinator** — selects the workflow and keeps scope/evidence/gates coherent.
- **Hunter** — strengthens the idea and finds value, evidence and useful extensions.
- **Skeptic** — tries to falsify the idea and identifies unsupported claims, hidden costs, risks and simpler alternatives.
- **Referee** — issues one verdict: promote, repair, combine, defer, or reject.
- **Reflector** — converts experience and feedback into proposed reusable learning.
- **Recorder** — preserves state, provenance, approvals, disagreement, history and version changes.

These are profiles interpreted by the available LLM/client. The portable contract does not claim that an XLSX file itself runs autonomous agents.

## Reflection loop

`run -> observe -> reflect -> propose improvement -> Skeptic -> Referee -> human approve/reject -> apply approved change -> preserve old state -> log version`

Observed behavior is not automatically a personal fact. A model noticing that the user repeatedly requests a certain format may propose it as a preference; it must not activate that preference without approval when it would materially alter future behavior.

## Beginner path

1. Pick one recurring task or pain point.
2. Use Quick setup.
3. Run one workflow.
4. Review whether the structure helped.
5. Run Reflect & Improve.
6. Keep, discard, or repair the harness.
7. Add architecture only when the current container stops being enough.

## Graduation paths

The same contract can later move to richer storage, Skills, connectors/MCP, automation platforms, databases, or professional implementation. The point of the starter harness is not to replace those options; it is to clarify the problem and the operating brief before spending more time or money.
