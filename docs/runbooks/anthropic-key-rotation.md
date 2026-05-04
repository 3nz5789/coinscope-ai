# Anthropic API Key Rotation Runbook

**Purpose:** Rotate Anthropic API keys without breaking the Scoopy runtime, the in-product agent, scheduled jobs, or CI eval runs. Maintain a clean audit trail. Always overlap old and new keys during cutover — never run with a single live key during rotation.

**Owner:** Mohammed
**Last reviewed:** 2026-05-04
**Cadence:** Quarterly (scheduled, first Monday of each quarter) + on any triggered event below.

---

## Key inventory

| Key alias        | Used by                                                    | Monthly cap | Stored in                                  |
|------------------|------------------------------------------------------------|-------------|--------------------------------------------|
| `prod-runtime`   | Telegram bot, in-product agent on coinscope.ai, cron jobs  | $300        | VPS env (`/etc/scoopy/.env`), 1Password    |
| `ci-evals`       | GitHub Actions `evals.yml` workflow only                   | $100        | GitHub repo secrets, 1Password             |

If a third key appears anywhere, rotation is incomplete. Stop and reconcile before proceeding.

## When to run

**Scheduled:** First Monday of each quarter. Calendar event seeds the next rotation 90 days out.

**Triggered (rotate immediately):**
- Key value pasted into chat, log, screenshot, commit, or any non-secret store
- Anomalous spend (>2x 7-day rolling average without a deploy event)
- Anthropic console flags the key
- Departure of any contractor with key access
- After any incident where the key path was even possibly exposed

## Pre-flight

Run all three blocks before generating a new key. If any step fails, abort — do not begin rotation on a system that is not currently healthy, or you will not be able to distinguish rotation breakage from pre-existing breakage.

**A. Verify current state**
- Both keys present and active in Anthropic console.
- Month-to-date spend per key matches expected pattern. Snapshot to `docs/runbooks/_artifacts/key-rotation-YYYY-MM-DD-pre.txt`.
- `evals/baseline_*.json` (current) green on the last nightly audit run.
- `prod-runtime` is serving — `/health` on the engine API responds, and Scoopy `/status` ping returns the canonical disclaimer.

**B. Make space**
- Anthropic console workspace allows two active keys per alias temporarily (default: yes).
- Open the rotation log: `docs/runbooks/_artifacts/key-rotation-YYYY-MM-DD.md`. Template at end of this runbook.

**C. Confirm scope**
- Decide which alias(es) to rotate. Default: rotate `ci-evals` first (lower blast radius), then `prod-runtime`.
- Both keys can be rotated in the same session, but Phase 6 (decommission) is per-key with a 24h delay.

---

## Steps

### 1. Generate

In Anthropic console:

```
API Keys → Create Key
Name: <alias>-YYYY-MM-DD          # e.g., ci-evals-2026-08-04
Monthly spend cap: <per inventory table above>
```

Copy the new value into 1Password under `CoinScopeAI / Anthropic / <alias>` as a **new entry**. Do not overwrite the existing entry.

### 2. Stage (do not cut over yet)

For `ci-evals`:

```
GitHub repo → Settings → Secrets and variables → Actions
Add: ANTHROPIC_API_KEY_NEW   = <new value>
Keep: ANTHROPIC_API_KEY      = <old value, untouched>
```

For `prod-runtime`:

```bash
ssh root@api.coinscope.ai
sudo tee -a /etc/scoopy/.env <<'EOF'
ANTHROPIC_API_KEY_NEW=<new-key>
EOF
# do not remove the existing ANTHROPIC_API_KEY line
```

### 3. Smoke test (new key only)

For `ci-evals`: open a throwaway PR that flips the workflow env to read `ANTHROPIC_API_KEY_NEW`. Confirm the eval preview run is green (12/12 fixtures, drift=0). Close the PR without merging.

For `prod-runtime`:

```bash
python -m scoopy_runtime.smoke --key-env ANTHROPIC_API_KEY_NEW
```

Expected:
```
fixtures: 12/12 pass   drift: 0   disclaimer: present
```

Do not restart any service yet.

### 4. Cut over

For `ci-evals`:

```
GitHub Secrets: update ANTHROPIC_API_KEY = <new value>
Keep ANTHROPIC_API_KEY_NEW for now (same value, harmless until Phase 6)
```

For `prod-runtime`:

```bash
ssh root@api.coinscope.ai
sudo sed -i 's/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=<new-value>/' /etc/scoopy/.env

# restart in order, 30s between each, tail logs
sudo systemctl restart scoopy-bot       && sleep 30
sudo systemctl restart scoopy-agent     && sleep 30
sudo systemctl restart scoopy-cron
sudo journalctl -u scoopy-bot -u scoopy-agent -u scoopy-cron -f
```

### 5. Verify

Run all three:

1. Send Scoopy a `/status` ping. Expect normal response including the canonical disclaimer.
2. Trigger a manual eval run on `main`:
   ```bash
   gh workflow run evals.yml --ref main
   gh run watch
   ```
   Expect green.
3. Anthropic console:
   - New key shows non-zero usage in the last 5 minutes.
   - Old key usage flatlines.

If any step fails, **roll back per §Rollback below — do not "just try again."**

### 6. Decommission old key

Wait **24 hours** after Phase 5 with the old key still active in Anthropic console (so any in-flight retry path doesn't 401). Then:

```
Anthropic console: revoke old key
GitHub Secrets:    remove ANTHROPIC_API_KEY_NEW
VPS:               sudo sed -i '/^ANTHROPIC_API_KEY_NEW=/d' /etc/scoopy/.env
1Password:         move old entry to Archive / Anthropic / <alias>-rotated-YYYY-MM-DD
```

Snapshot post-state to `docs/runbooks/_artifacts/key-rotation-YYYY-MM-DD-post.txt`.

---

## Post-rotation verification (24h after Phase 6)

- New key spend > $0 in Anthropic console
- Old key spend = $0 since revocation timestamp
- Last 24h of nightly audit runs: green
- No 401/403 in:
  ```bash
  sudo journalctl -u scoopy-bot -u scoopy-agent -u scoopy-cron --since "1 day ago" | grep -E '40[13]'
  ```

If any item is red, open a Linear issue under `COI-` prefix tagged `incident/auth`.

---

## Rollback

Rollback is only possible during Phase 4–5, **before** Phase 6. After revocation, the old key is gone.

**For `ci-evals`:**

```
GitHub Secrets: revert ANTHROPIC_API_KEY to the prior value (still in 1Password)
Re-run any failed workflow
```

**For `prod-runtime`:**

```bash
ssh root@api.coinscope.ai
sudo sed -i 's/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=<old-value>/' /etc/scoopy/.env
sudo systemctl restart scoopy-bot scoopy-agent scoopy-cron
```

Then re-run Phase 5 verification against the restored old key. Investigate the failure before retrying rotation.

---

## Anti-patterns (do not do)

- Single-step swap (revoke old, paste new, restart). Always overlap.
- Reuse the same key alias for both runtimes "just for testing." Two aliases, two scopes, two caps.
- Paste a new key value into chat with Scoopy or any LLM surface, including this one.
- Rotate during a drift event or active incident. Stabilize first.
- Skip the 24-hour decommission delay. In-flight retries will 401 and you will page yourself for a non-issue.
- Edit `/etc/scoopy/.env` without `sudo sed` (or equivalent atomic write). Partial writes break startup.

---

## Rotation log template

Save as `docs/runbooks/_artifacts/key-rotation-YYYY-MM-DD.md`:

```markdown
# Key rotation — YYYY-MM-DD

Operator: Mohammed
Trigger:  scheduled | exposure | spend-anomaly | departure | incident
Keys:     ci-evals | prod-runtime | both

Pre-flight (A,B,C):  pass | fail (reason)
Phase 1 (generate):       <timestamp>
Phase 2 (stage):          <timestamp>
Phase 3 (smoke):          <timestamp>   fixtures: 12/12   drift: 0
Phase 4 (cut over):       <timestamp>
Phase 5 (verify):         <timestamp>   anomalies: none | <list>
Phase 6 (decommission):   <timestamp + 24h>

Notes:
-
```

---

**Cross-references:**
- `docs/runbooks/vps-engine-restart.md` — restart procedure for the engine processes touched in Phase 4
- `evals/baseline_*.json` — canonical eval baseline checked in Phases A and 3
- `.github/workflows/evals.yml` — CI workflow that consumes `ANTHROPIC_API_KEY`
