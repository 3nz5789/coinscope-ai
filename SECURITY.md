# Security Policy

## Scope

**In scope:**
- Engine API (`api.coinscope.ai`) and all endpoints
- Dashboard (`app.coinscope.ai`) — auth, session, billing
- Binance exchange adapter and API key handling
- Risk gate bypass or kill-switch circumvention
- Position sizing manipulation
- Authentication and access control

**Out of scope:**
- Binance or other third-party exchange vulnerabilities
- Telegram API vulnerabilities
- Issues requiring physical access to infrastructure
- Theoretical vulnerabilities with no demonstrated impact

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **security@coinscope.ai**

Include:
- Clear description of the vulnerability
- Steps to reproduce
- Affected component and version/commit
- Potential impact assessment
- Suggested fix (optional)

---

## Response Timeline

| Stage | Target |
|---|---|
| Acknowledgement | Within 48 hours |
| Initial severity assessment | Within 5 business days |
| Fix deployed (critical) | Within 14 days |
| Fix deployed (high) | Within 30 days |
| Public disclosure | After fix deployed, coordinated with reporter |

---

## Severity Definitions

### Sev-1 — Escalated immediately

- Risk gate bypass — order placed without a logged gate decision
- Kill-switch circumvention — new entries accepted when kill switch is engaged
- Circuit breaker bypass — trading continues after a tripped breaker
- Exchange API key or secret exposure (in logs, URLs, responses, or committed files)
- Unauthorised order placement on any exchange account
- Authentication bypass
- Position size exceeding the 2% hard cap via any code path

### Sev-2 — High priority

- Information disclosure of user trade data or PII
- Privilege escalation within the dashboard
- Telegram bot command injection

### Sev-3 — Normal priority

- Logic errors in non-execution paths
- UI/dashboard vulnerabilities with limited financial impact

---

## Supported Versions

Only the latest `main` branch is actively supported.

---

## Disclosure Policy

We follow coordinated disclosure. Please give us reasonable time to fix before going public. We will credit reporters in our changelog unless anonymity is requested.
