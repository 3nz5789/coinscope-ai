# Contributing to CoinScopeAI

**Status:** current
**Audience:** anyone committing to this repo
**Related:** `README.md`, `docs/onboarding/new-developer-guide.md`, `docs/testing/testing-strategy.md`

---

## Validation freeze (2026-04-10 to 2026-04-30)

While validation is running, the following are **off-limits** without explicit sign-off:

- Module restructuring inside `coinscope_trading_engine/`.
- Renaming exported symbols or changing import paths in the engine.
- Changes to risk thresholds, Kelly parameters, or circuit-breaker logic.
- Switching from Binance Testnet to mainnet.
- Introducing new exchanges.

Doc changes, new tests, bug fixes with PR review, and infra-adjacent edits (`archive/`, `docs/`, `scripts/`) are allowed.

## Branching

- `main` — always deployable. Protected: PR + CI green required.
- `develop` — integration branch. CI runs here too.
- Feature branches: `feat/<scope>-<short-description>` e.g. `feat/risk-heat-cap-tests`.
- Fix branches: `fix/<scope>-<short-description>` e.g. `fix/ws-reconnect-backoff`.
- Doc-only branches: `docs/<short-description>`.
- Experiments: `spike/<short-description>` — never merged into `main`.

## Commit messages

Use Conventional-Commit-style prefixes. Format: `type(scope): subject` in the imperative present tense.

Types in use: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ops`, `ci`.

Examples:

- `fix(risk): clamp Kelly to 2% after regime multiplier`
- `feat(api): add /performance/daily endpoint`
- `docs(onboarding): add first-week checklist`
- `ops(archive): move fixed/ patches to archive`

Keep the subject line under 72 characters. Put detail in the body, including the *why*.

## Pull requests

Every PR should have:

- **Title** following the commit-message convention above.
- **Summary** describing what changed and why in two to five sentences.
- **Linear / issue link** if one exists.
- **Risk note** — one of `safe`, `engine-adjacent`, `risk-logic`, `exchange-adjacent`. Risk-logic and exchange-adjacent PRs are held during validation.
- **Testing** — what you ran locally, what CI covers, what you did NOT test and why.
- **Rollback plan** if the change is more than a trivial fix.

Reviewer expectations:

- At least one approving review. Two reviewers for anything touching `risk/`, `execution/`, the scorer, or the billing webhook.
- Reviewer reads the diff in full, not just the title, and checks the linked tests actually cover the change.
- Reviewer must block PRs that widen risk surface area without corresponding tests.

## Testing expectations

- Every `feat` or `fix` PR ships with a test that fails on `main` and passes on the branch, unless the change is provably untestable (in which case the PR must say so explicitly).
- Risk and execution code paths require tests in `coinscope_trading_engine/tests/`.
- Billing PRs run `pytest tests/test_billing_*` locally before review.
- CI: `.github/workflows/ci.yml` runs `pytest` against the full repo. A red CI blocks merge.

See `docs/testing/testing-strategy.md` for the full test taxonomy.

## Adding or updating docs

Every non-trivial code change updates docs in the same PR. Checklist:

- New endpoint? Update `docs/api/backend-endpoints.md`.
- New env var? Update `.env.example` and `docs/backend/configuration.md`.
- New module? Add a short section to `docs/architecture/component-map.md`.
- New failure mode? Add to `docs/runbooks/troubleshooting.md`.
- Architectural decision? Open an ADR in `docs/decisions/adr-XXXX-<slug>.md` using the template at `docs/decisions/TEMPLATE.md`.

Docs use Markdown, start with a `Status: current | draft | planned` header, and link to related docs at the top.

## Secrets

- Never commit `.env`, `*.key`, or `billing_subscriptions.db` (already in `.gitignore`).
- Rotate Binance testnet keys if they ever appear in a diff or a log. Testnet-only keys still deserve hygiene.
- Stripe keys go in the environment. Never hardcode.

## Style

- Python: `black` formatting. `ruff` for linting. Type hints required on public functions.
- Imports: standard-library, third-party, local — separated by a blank line.
- Logging: use `logging.getLogger(__name__)`. No `print` in engine or API code.
- Async: use `asyncio`, not threads, for the engine loop. Threads are acceptable for isolated I/O workers only.

## CoinScopeAI Division Standards

Agents in `agency-agents/coinscopeai/` must be operational, domain-aware, and safe for high-stakes product work.

### Required frontmatter
Every agent file must include:
- `name`
- `description`
- `color`
- `tools`

Example:
---
name: CoinScopeAI Risk Guardian
description: Blocks unsafe changes involving orders, leverage, billing, auth, secrets, and trust-sensitive workflows.
color: orange
tools:
  - codebase
  - tests
  - docs
---

### Required sections
Every `agency-agents/coinscopeai/*.md` agent must contain these sections in order:
1. `# Identity`
2. `# Mission`
3. `# When to use`
4. `# Inputs required`
5. `# Workflow`
6. `# Guardrails`
7. `# Deliverables`
8. `# Handoff`
9. `# Success criteria`

### CoinScopeAI-specific rules
- Agents must optimize for correctness over speed when changes touch trading, billing, auth, or user trust.
- Agents must explicitly identify blast radius before recommending implementation steps.
- Agents must distinguish between read-only diagnosis, proposed changes, and approved execution.
- Agents must name failure modes, not just happy paths.
- Agents must require tests for critical-path changes.
- Agents must mention rollback, kill switch, or disable path for risky changes.
- Agents must not recommend coupling exchange adapter logic with strategy logic.
- Agents must not allow silent fallback to stale market data for actionable trading features.
- Agents must classify risk across at least one of: funds, uptime, trust, data integrity, security.

### Preferred deliverable style
CoinScopeAI agents should produce concise, decision-ready outputs:
- Context summary
- Findings
- Risks
- Recommended action
- Validation plan
- Rollback or recovery path

### Naming conventions
- Folder: `agency-agents/coinscopeai/`
- File names: `coinscopeai-{role-name}.md`
- Use lowercase kebab-case
- Keep names specific and operational, not generic

### Scope discipline
Do not add a new CoinScopeAI agent if an existing one can be extended safely.
New agents should exist only when they represent a distinct workflow, risk area, or decision pattern.

### Testing expectation
Any agent that can influence code affecting:
- signal generation
- scoring
- exchange integrations
- order lifecycle
- billing
- auth
must require explicit validation steps and regression coverage.

### Review checklist for new CoinScopeAI agents
- Is the role distinct?
- Does it have clear activation triggers?
- Are guardrails concrete and enforceable?
- Does it define handoff correctly?
- Does it improve safety or leverage for CoinScopeAI?

## When in doubt

Ask in the project Slack / Linear before merging. Capital preservation > velocity. The engine trades real-feeling money on testnet today and real money later — defensive reviews are the culture we want.
