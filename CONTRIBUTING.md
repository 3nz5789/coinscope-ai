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

## When in doubt

Ask in the project Slack / Linear before merging. Capital preservation > velocity. The engine trades real-feeling money on testnet today and real money later — defensive reviews are the culture we want.
