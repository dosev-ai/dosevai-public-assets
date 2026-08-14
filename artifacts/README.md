# Working artifacts

This directory contains public-safe, versioned working artifacts that can be used directly by people or read by compatible AI assistants.

Each artifact owns its own onboarding contract. Start with its `README.md`, then read its `manifest.json` before selecting a version.

## Rules

- Released version folders are immutable. Publish a new version instead of rewriting an old one.
- A repository artifact is not an autonomous runtime. The user's AI assistant interprets the artifact.
- Do not assume that every AI product can read URLs, repositories, spreadsheets, or write files in the same way.
- Do not silently mutate user context or operating rules. Follow the artifact's approval policy.
- Do not put secrets, credentials, employer-confidential data, or private governance identifiers in public artifacts.

## Available artifacts

- `portable-ai-harness/` - a provider-neutral spreadsheet harness for exploring recurring AI workflows, role separation, testing, reflection, and versioned learning.
