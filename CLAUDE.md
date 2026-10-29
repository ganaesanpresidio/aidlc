# CLAUDE.md

Project memory for Claude Code. Keep this file short; details live in `docs/`.

## What this repo is

The AI-DLC playbook for an **Expense Management Platform** (banking & finance).
It defines eight activities across three phases — Discover, Build, Deploy & Monitor —
each with its actors, tools, agents, skills, workflow, hooks and human gates.

Start here: [docs/00-overview.md](docs/00-overview.md).

## Golden rules

1. **AI proposes, humans decide.** Never mark a gate as approved. Only the named human
   edits files in `aidlc-docs/approvals/`.
2. **Follow the activity file.** Before any work, read the matching file in `docs/`
   (e.g. `docs/2-build/bld-01-build-units-in-bolts.md`) and follow its workflow steps.
3. **Respect the gates.** No code under `src/` or `infra/` before spec sign-off (DIS-02);
   no `src/<unit>/` code before `lld-<unit>.md` is approved (DIS-04). Never deploy to prod.
4. **Ask before guessing.** Unknown policy limits, approvers or thresholds are OPEN QUESTIONS.
5. **No real data.** No real PII, receipts, card or bank numbers anywhere. Use synthetic data.
6. **Use the glossary.** Terms come from `aidlc-docs/glossary/policy-glossary.md`.
7. **Small bolts.** Keep each change small enough to review in one sitting.

## Repo layout

```text
docs/                 Playbook (this is the source of truth for the method)
  00-overview.md      Phases, roles, gates, artifact layout
  _TEMPLATE.md        Required structure for every activity file
  hooks-catalog.md    All hooks + combined settings.json
  references.md       Links for every tool, skill and method
  1-discover/         DIS-01 … DIS-04
  2-build/            BLD-01 … BLD-02
  3-deploy-monitor/   DEP-01 … DEP-02
aidlc-docs/           Project artifacts created while running the playbook (created on first use)
.claude/              Shared Claude Code settings (hooks/agents added during rollout)
```

## Writing or editing docs

- Copy `docs/_TEMPLATE.md` for any new activity. Keep every H2 heading, in order, same wording.
- File names: lowercase kebab-case with the activity ID prefix, e.g. `bld-01-build-units-in-bolts.md`.
- Update `version`, `last_updated` and the Change log on every meaningful change.
- Use relative links. Run `npx markdownlint-cli2 "**/*.md"` before committing.

## Commands

```bash
npx markdownlint-cli2 "**/*.md"
```
