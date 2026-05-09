# Security Policy

## Scope

This policy covers the CoinScopeAI trading engine, dashboard, and all supporting infrastructure.

**In scope:**
- Engine API (`api.coinscope.ai`)
- Dashboard (`app.coinscope.ai`)
- Binance exchange adapter and API key handling
- Authentication and session management
- Risk gate bypass vulnerabilities
- Kill-switch circumvention

**Out of scope:**
- Binance or third-party exchange vulnerabilities
- Telegram API vulnerabilities
- Issues requiring physical access

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **security@coinscope.ai**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Your suggested fix (optional)

## Response Timeline

| Stage | Target |
|---|---|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix deployed | Within 14 days for critical issues |
| Public disclosure | After fix is deployed (coordinated) |

## Critical Priorities

The following are treated as Sev-1 and escalated immediately:

- Any bypass of the risk gate or kill switch
- Exposure of exchange API keys or secrets
- Unauthorized order placement
- Authentication bypass

## Supported Versions

Only the latest `main` branch is actively supported.
