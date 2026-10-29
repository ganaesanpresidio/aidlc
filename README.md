# AI-DLC Playbook — Expense Management Platform

The AI-Driven Development Life Cycle (AI-DLC) playbook for building an end-to-end expense management platform for banking & finance, run on Claude Code.

> AI plans, proposes and builds; humans set intent, decide at every gate and own the outcome — delivered in bolts of hours or days, with all context kept in the repo.

Source: `AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx` (slides 1–3). Based on the AWS AI-DLC method and the open-source `awslabs/aidlc-workflows`.

## Contents

| Phase | Activity | File |
| --- | --- | --- |
| — | Overview, roles, gates, artifact layout | [docs/00-overview.md](docs/00-overview.md) |
| Discover | DIS-01 Intent → stories (Mob Elaboration) | [dis-01-intent-to-stories.md](docs/1-discover/dis-01-intent-to-stories.md) |
| Discover | DIS-02 Policy & approval rules as a domain model | [dis-02-policy-approval-domain-model.md](docs/1-discover/dis-02-policy-approval-domain-model.md) |
| Discover | DIS-03 Units of work & NFRs | [dis-03-units-of-work-and-nfrs.md](docs/1-discover/dis-03-units-of-work-and-nfrs.md) |
| Discover | DIS-04 HLD & LLD per unit + design approval | [dis-04-hld-lld-design-approval.md](docs/1-discover/dis-04-hld-lld-design-approval.md) |
| Build | BLD-01 Build each unit in bolts | [bld-01-build-units-in-bolts.md](docs/2-build/bld-01-build-units-in-bolts.md) |
| Build | BLD-02 Verify, review & secure | [bld-02-verify-review-secure.md](docs/2-build/bld-02-verify-review-secure.md) |
| Deploy & Monitor | DEP-01 Deploy with IaC & release gates | [dep-01-deploy-iac-release-gates.md](docs/3-deploy-monitor/dep-01-deploy-iac-release-gates.md) |
| Deploy & Monitor | DEP-02 Operate, spend analytics & feedback loop | [dep-02-operate-analytics-feedback.md](docs/3-deploy-monitor/dep-02-operate-analytics-feedback.md) |
| — | All hooks in one place | [docs/hooks-catalog.md](docs/hooks-catalog.md) |
| — | References and links | [docs/references.md](docs/references.md) |
| — | Template for new activity files | [docs/_TEMPLATE.md](docs/_TEMPLATE.md) |

## Every activity file has the same structure

Front matter (id, phase, actors, version, source, previous/next) and these sections, in this order:

At a glance · 1 Objective · 2 Roles and responsibilities · 3 Entry criteria · 4 Tools, MCP servers and agents · 5 Skills · 6 Workflow · 7 Hooks · 8 Outputs and artifacts · 9 Exit criteria · 10 Starter prompts · 11 Best practices · 12 Anti-patterns · 13 References · Change log

## How to use

1. Read [docs/00-overview.md](docs/00-overview.md) for roles, gates and the artifact layout.
2. Open the activity you are in. Follow section **6. Workflow** step by step.
3. Use the **starter prompts** in section 10 with Claude Code.
4. Roll out hooks and subagents when the team is ready — see [docs/hooks-catalog.md](docs/hooks-catalog.md). They are documented here but **not yet active** in `.claude/settings.json`.

## Repository layout

```text
.
├── CLAUDE.md                 Claude Code project memory
├── README.md
├── .claude/settings.json     Shared Claude Code settings (committed)
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .markdownlint.json
└── docs/
    ├── 00-overview.md
    ├── _TEMPLATE.md
    ├── hooks-catalog.md
    ├── references.md
    ├── 1-discover/
    ├── 2-build/
    └── 3-deploy-monitor/
```

## Contributing

1. Branch from `main`: `docs/<id>-<short-change>` (e.g. `docs/bld-02-add-dast`).
2. New activity → copy `docs/_TEMPLATE.md`; keep all headings and their order.
3. Bump `version` and `last_updated`, add a Change log row.
4. Lint before you push:

   ```bash
   npx markdownlint-cli2 "**/*.md"
   ```

5. Open a PR. Changes to gates, hooks or approval rules need Architect review.

Suggested `.github/CODEOWNERS` once the repo is on GitHub:

```text
/docs/hooks-catalog.md   @<architect-handle>
/.claude/                @<architect-handle>
/aidlc-docs/approvals/   @<architect-handle> @<solution-owner-handle>
```

## Security

- Never commit secrets, webhook URLs, real PII, receipts or bank/card data.
- Personal Claude settings go in `.claude/settings.local.json` (git-ignored).
