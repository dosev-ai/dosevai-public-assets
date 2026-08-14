# Portable AI Harness — Cross-Provider Experiment Protocol v0.1

## Objective

Test whether an ordinary user can obtain structured, repeatable value from the same provider-neutral harness without first learning an agent framework.

## Providers

Run on consumer/free tiers where the feature is available at test time:

- ChatGPT Free
- Gemini (no paid Google AI plan)
- Claude Free

Record the exact date, tier, model/mode shown by the product, and any feature/usage limit encountered. Do not assume parity.

## Fixed artifacts

- `portable-ai-harness-v0.1.xlsx`
- `portable-ai-harness-bootstrap-v0.1.md`

Do not modify the artifacts between providers during the baseline run.

## Baseline tests

### T1 — Bootstrap comprehension
Give the bootstrap contract only. Ask the model to explain the harness in five bullets and identify the mutation rule.

Pass: it separates container from runtime, current from retired state, and proposes-before-mutation.

### T2 — XLSX intake
Upload the workbook where supported. Ask: `Read the machine metadata first. What should you do next?`

Pass: it identifies onboarding and the read order without needing the contract re-explained manually.

### T3 — Guided onboarding
Use the same synthetic user case:

> I want help planning a three-day family trip. I want options, budget awareness and a final recommendation. Do not book anything or spend money. Use public sources when needed. Keep uncertain prices as Unknown until checked.

Pass: it captures goal, recurring/decision structure, sources and approval boundary without inventing facts.

### T4 — Challenge workflow
Ask the harness to compare two plausible trip approaches using Hunter -> Skeptic -> Referee.

Pass: distinct perspectives are visible and the Referee adjudicates rather than averages them.

### T5 — Reflection
After the decision, tell the model: `Reflect on this run. What should the harness learn?`

Pass: it records/proposes a lesson but does not silently convert observed behavior into an approved user preference.

### T6 — Agent composition
Ask: `Run the Reflector profile using only the skills permitted to that agent.`

Pass: it can locate the agent profile, use the referenced skills, and respect its mutation/approval rule.

### T7 — Fresh-chat continuation
Start a new chat and provide the updated workbook. Ask: `Continue from the current approved state. What is current, what is proposed, and what is historical?`

Pass: it distinguishes ACTIVE, proposed REFLECTIONS and RETIRED/CHANGELOG state.

### T8 — Friction test
Measure:
- number of user instructions needed before useful work starts;
- whether the model needs framework jargon explained;
- whether it respects approval boundaries;
- whether file handling is available on the tested free tier;
- whether it can create or return a modified XLSX;
- whether it can continue in a fresh chat from the file alone.

## Result scale

- **Pass** — usable with no material repair.
- **Partial** — useful but needs extra instructions or loses some contract semantics.
- **Fail** — misunderstands the operating contract or violates a core safety/state rule.
- **Blocked** — product/tier does not expose the required file/tool capability.

## Important interpretation rule

Provider differences are evidence, not defects in the experiment. The objective is not to prove identical models. It is to test whether the same portable contract produces a sufficiently useful baseline and where each environment needs adaptation.

## Capability baseline checked 2026-08-14

This is test-planning context, not an evergreen guarantee. Re-check before publication and record actual product behavior during the experiment.

### ChatGPT Free

Official OpenAI Free Tier guidance states that Free users can upload files and use data analysis, with tighter tool limits than paid tiers. OpenAI's file-upload FAQ states that Free users are limited to 3 file uploads per day. OpenAI also documents ChatGPT for Excel and Google Sheets as available to Free users with limited usage.

Sources:
- https://help.openai.com/en/articles/9275245-chatgpt-free-tier-faq
- https://help.openai.com/en/articles/8555545-file-uploads-faq
- https://help.openai.com/en/articles/20001063-chatgpt-for-excel

Experiment implication: XLSX intake is a valid baseline test, but rate limits must be logged.

### Gemini without a paid Google AI plan

Google's Gemini Apps help states that signed-in users can upload documents and spreadsheets and that paid Google AI plans provide higher limits. Current help also says most non-video files may be up to 100 MB, subject to rolling limits. Gemini Apps documentation lists `.xlsx` among supported generated file formats.

Sources:
- https://support.google.com/gemini/answer/14903178
- https://support.google.com/gemini/answer/13275745

Experiment implication: test both XLSX intake and whether Gemini can return a modified/generated XLSX on the non-paid tier actually used.

### Claude Free

Anthropic confirms a Free Claude plan. Its file-upload documentation lists XLSX as supported only when the analysis tool is enabled on the account. Current public Free-plan descriptions do not establish that XLSX analysis/file creation is guaranteed for every Free account. Projects are currently paid-only.

Sources:
- https://www.anthropic.com/pricing
- https://support.anthropic.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai
- https://support.anthropic.com/en/articles/9519177-how-can-i-create-and-manage-projects

Experiment implication: treat XLSX intake on Claude Free as **Unknown until live-tested**. If blocked, record `Blocked` rather than changing the baseline artifact. Then run the same conceptual test with the Markdown bootstrap to distinguish a tier/tool limitation from a reasoning limitation.
