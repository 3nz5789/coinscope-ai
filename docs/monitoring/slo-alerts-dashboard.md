# SLOs, Alert Rules, and Prometheus Dashboard Spec

**Status:** current — P0 validation phase
**Audience:** operator, on-call, and any future SRE
**Phase:** P0 — Binance Testnet only (May 2026)
**Related:**
- [`../ops/telegram-alerts.md`](../ops/telegram-alerts.md) — Telegram format conventions
- [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md) — kill switch protocol
- [`../../coinscope_trading_engine/monitoring/prometheus_metrics.py`](../../coinscope_trading_engine/monitoring/prometheus_metrics.py) — metric definitions
- [`../../prometheus.yml`](../../prometheus.yml) — scrape config

---

## Part 1 — Service Level Objectives

SLOs define what "working correctly" means for each engine subsystem.
Violations trigger the alert rules in Part 2.

During P0 the engine runs on testnet with a 40-user cap. SLOs here are
intentionally conservative — they exist to surface real problems, not to
guarantee uptime of a production system.

### SLO-01 — Engine Liveness

| Field | Value |
|---|---|
| **What** | `/health` returns HTTP 200 |
| **Target** | 99% of checks over any 1-hour window |
| **Measurement** | `up{job="coinscopeai_engine"}` Prometheus scrape result |
| **Breach** | Engine offline > 36 seconds in any rolling hour |
| **Alert** | `EngineDown` — CRITICAL |
| **Action** | SSH to VPS → `docker compose up -d --force-recreate` |

### SLO-02 — Scan Cycle Freshness

| Field | Value |
|---|---|
| **What** | A full scan cycle completes at least once every 5 minutes |
| **Target** | 95% of 5-minute windows contain ≥ 1 completed scan |
| **Measurement** | `rate(coinscopeai_scans_total[5m]) > 0` |
| **Breach** | No scan in 5+ consecutive minutes |
| **Alert** | `ScanStalled` — WARN |
| **Action** | Check worker health. If scan loop is stuck, restart engine. |

### SLO-03 — Scan Latency

| Field | Value |
|---|---|
| **What** | Full 6-pair scan completes within 30 seconds |
| **Target** | p95 scan duration ≤ 30s over any 1-hour window |
| **Measurement** | `histogram_quantile(0.95, rate(coinscopeai_scan_duration_seconds_bucket[1h]))` |
| **Breach** | p95 > 30s |
| **Alert** | `ScanSlow` — WARN |
| **Action** | Check Binance Testnet latency. Check rate-limit token consumption. |

### SLO-04 — WebSocket Data Freshness

| Field | Value |
|---|---|
| **What** | No symbol data gap > 60 seconds |
| **Target** | 99% of 1-minute windows have zero stream gaps > 60s across all tracked symbols |
| **Measurement** | WS reconnect counter + `/ready` adapter health |
| **Breach** | Any symbol goes > 60 seconds without a kline update |
| **Alert** | `StreamGap` — WARN |
| **Action** | Check WS reconnect counter. If gap persists > 5 min, engage kill switch and investigate. |

### SLO-05 — Circuit Breaker False-Open Rate

| Field | Value |
|---|---|
| **What** | Circuit breaker must not open due to a bug or bad data — only due to real risk threshold breach |
| **Target** | Zero unexpected breaker trips (any trip must be traceable to a threshold breach or operator action) |
| **Measurement** | Manual review of trip_history after every trip |
| **Breach** | Trip with no corresponding threshold breach in the journal |
| **Alert** | `CircuitBreakerOpen` fires on every trip — CRITICAL |
| **Action** | Read `/journal` before resetting. If no threshold breach found, treat as a bug — open incident. |

### SLO-06 — Binance REST Error Rate

| Field | Value |
|---|---|
| **What** | Binance REST 5xx error rate stays below 1% of calls |
| **Target** | `rate(coinscopeai_api_requests_total{status="5xx"}[5m]) / rate(coinscopeai_api_requests_total[5m]) < 0.01` |
| **Breach** | > 1% 5xx rate over any 5-minute window |
| **Alert** | `BinanceRestErrors` — WARN |
| **Action** | Check Binance Testnet status. If persistent, engage kill switch — engine may be trading on stale data. |

### SLO-07 — Position Heat Cap Compliance

| Field | Value |
|---|---|
| **What** | Total deployed capital must never exceed 80% |
| **Target** | `coinscopeai_total_exposure_pct` ≤ 80 at all times |
| **Breach** | Any reading above 80% |
| **Alert** | `ExposureHigh` — CRITICAL |
| **Action** | Immediate manual review. Do not open new positions. If > 80% — investigate sizing bug. |

### SLO-08 — Daily P&L Floor (Alert Zone)

| Field | Value |
|---|---|
| **What** | Daily loss must not approach the 5% hard limit without operator awareness |
| **Target** | Alert fires at 3.5% loss (70% of the 5% limit) to give operator time to act |
| **Measurement** | `coinscopeai_daily_pnl_usdt` vs known equity baseline |
| **Breach** | Daily loss > 3.5% of starting equity |
| **Alert** | `DailyLossWarning` — WARN at 3.5%; `DailyLossLimit` — CRITICAL at 5% |
| **Action** | At 3.5%: reduce new position sizes. At 5%: gate auto-trips, verify breaker fired. |

---

## Part 2 — Prometheus Alert Rules

Save as `prometheus-alert-rules.yml` at repo root alongside `prometheus.yml`.

```yaml
# prometheus-alert-rules.yml
# CoinScopeAI — P0 Validation Alert Rules
# Aligned with SLOs in docs/monitoring/slo-alerts-dashboard.md

groups:

  - name: coinscopeai.liveness
    rules:

      # SLO-01 — Engine down
      - alert: EngineDown
        expr: up{job="coinscopeai_engine"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Engine is unreachable"
          description: >
            CoinScopeAI engine has not responded to scrapes for 1 minute.
            Action: SSH to VPS → docker compose up -d --force-recreate.

      # SLO-02 — Scan loop stalled
      - alert: ScanStalled
        expr: rate(coinscopeai_scans_total[5m]) == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "No scan cycles in 5 minutes"
          description: >
            coinscopeai_scans_total has not incremented in 5m.
            The scan loop may be stuck or the worker is dead.

  - name: coinscopeai.latency
    rules:

      # SLO-03 — Scan too slow
      - alert: ScanSlow
        expr: >
          histogram_quantile(0.95,
            rate(coinscopeai_scan_duration_seconds_bucket[1h])
          ) > 30
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "p95 scan duration > 30s"
          description: >
            Scan p95 latency has been above 30s for 15 minutes.
            Check Binance Testnet connectivity and rate-limit token levels.

      # Binance REST latency spike
      - alert: BinanceRestSlow
        expr: >
          histogram_quantile(0.95,
            rate(coinscopeai_api_latency_seconds_bucket[10m])
          ) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Binance REST p95 latency > 2s"
          description: "REST calls are slow. Check Binance Testnet status."

  - name: coinscopeai.risk
    rules:

      # SLO-05 — Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: coinscopeai_circuit_breaker_open == 1
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker is open — trading halted"
          description: >
            coinscopeai_circuit_breaker_open == 1. Read /journal before
            resetting. Verify a real threshold breach exists in the trade log.
            Action: POST /circuit-breaker/reset with a written reason.

      # SLO-07 — Exposure above hard cap
      - alert: ExposureHigh
        expr: coinscopeai_total_exposure_pct > 80
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Position heat cap breached (> 80%)"
          description: >
            Total deployed capital exceeds 80% (PCC v2 §8 hard cap).
            Do not open new positions. Investigate sizing logic immediately.

      # SLO-08 — Daily loss warning zone (3.5% of $10k baseline)
      - alert: DailyLossWarning
        expr: coinscopeai_daily_pnl_usdt < -350
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Daily loss approaching limit (> 3.5% of $10k baseline)"
          description: >
            Daily PnL below -$350. At 70% of the 5% hard limit.
            Consider reducing new position sizes. Gate auto-trips at -$500.

      # SLO-08 — Daily loss hard limit (5% of $10k baseline)
      - alert: DailyLossLimit
        expr: coinscopeai_daily_pnl_usdt < -500
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Daily loss limit hit (5% of $10k baseline)"
          description: >
            Daily PnL hit -$500. Risk gate circuit breaker should have
            auto-tripped. Verify coinscopeai_circuit_breaker_open == 1.

      # MAX_OPEN_POSITIONS=5 violation
      - alert: TooManyPositions
        expr: coinscopeai_open_positions > 5
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Open position count exceeds MAX_OPEN_POSITIONS=5"
          description: >
            coinscopeai_open_positions > 5. Violates PCC v2 §8.
            Investigate position tracker immediately.

  - name: coinscopeai.exchange
    rules:

      # SLO-06 — Binance REST error rate
      - alert: BinanceRestErrors
        expr: >
          rate(coinscopeai_api_requests_total{status="5xx"}[5m])
          /
          rate(coinscopeai_api_requests_total[5m])
          > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Binance REST 5xx error rate > 1%"
          description: >
            More than 1% of Binance REST calls returning 5xx over 5m.
            Engine may be on degraded data. Consider kill switch.

      # WebSocket reconnect burst
      - alert: WebSocketReconnectBurst
        expr: rate(coinscopeai_ws_reconnects_total[10m]) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "WebSocket reconnecting > 3x per 10 minutes"
          description: >
            WS reconnecting frequently. If stream gaps follow (> 60s),
            engage kill switch. See incident-binance-ws-disconnect-2026-04-18.md.

      # Rate-limit tokens critically low
      - alert: RateLimitLow
        expr: coinscopeai_rate_limit_tokens{channel="telegram"} < 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Telegram rate-limit tokens critically low (< 5)"
          description: "Alert delivery may be throttled. Reduce alert volume."
```

---

## Part 3 — Minimal Prometheus / Grafana Dashboard Spec

One dashboard, six panels. Minimum viable operator view for P0.
Panels ordered top-to-bottom, left-to-right by priority.

### Dashboard metadata

| Field | Value |
|---|---|
| Title | CoinScopeAI — P0 Operator View |
| UID | `coinscopeai-p0-operator` |
| Refresh | 15s |
| Time range default | Last 6 hours |
| Tags | `coinscopeai`, `p0`, `trading` |

---

### Panel 1 — Engine Status (Stat, row 1, full width)

Single-glance "is the engine alive and safe to trade?"

| Indicator | Query | Green | Red |
|---|---|---|---|
| Engine up | `up{job="coinscopeai_engine"}` | `== 1` | `== 0` |
| Circuit breaker | `coinscopeai_circuit_breaker_open` | `== 0` | `== 1` |
| Open positions | `coinscopeai_open_positions` | `≤ 5` | `> 5` |
| Exposure % | `coinscopeai_total_exposure_pct` | `≤ 70` | `> 80` |

Thresholds: green → safe, amber → exposure 70–80%, red → breaker open or engine down.

---

### Panel 2 — Daily P&L (Time series, row 2 left)

Running daily PnL vs warning and hard-stop reference lines.

```
Query A: coinscopeai_daily_pnl_usdt
  Legend: Daily PnL (USDT)
  Color:  green above 0 / red below 0

Reference lines (constant):
  -350 USDT  amber dashed  — warn zone (SLO-08 warning)
  -500 USDT  red solid     — hard limit (SLO-08 critical)
```

Y-axis: USDT. Time range: current trading day (00:00 UTC → now).

---

### Panel 3 — Scan Rate + Latency (Time series, row 2 right)

Confirm the scan loop is running and within latency budget.

```
Query A: rate(coinscopeai_scans_total[5m]) * 300
  Legend: Scans per 5 min
  Left Y-axis: count
  Color: blue

Query B: histogram_quantile(0.95, rate(coinscopeai_scan_duration_seconds_bucket[10m]))
  Legend: Scan p95 latency (s)
  Right Y-axis: seconds
  Color: orange
```

Annotation: horizontal reference line at 30s (SLO-03 threshold).

---

### Panel 4 — WebSocket Health (Time series, row 3 left)

Surface stream gaps and reconnect spikes before they affect signal quality.

```
Query A: rate(coinscopeai_ws_reconnects_total[10m]) * 600
  Legend: Reconnects per 10 min
  Color: amber if > 1 / red if > 3

Query B: coinscopeai_rate_limit_tokens{channel="telegram"}
  Legend: Telegram tokens remaining
  Color: red if < 5
```

---

### Panel 5 — Signal Score Distribution (Bar gauge, row 3 right)

Confirm the scoring engine produces a healthy spread — not clustering near 5.5.

```
Query: rate(coinscopeai_signal_score_bucket[1h])
  Type: Heatmap or bar gauge
  Legend: Signal score distribution
```

Healthy: spread across 5.5–10, meaningful volume above 8.
Warn: all scores in [5.5, 6.5] — edge erosion signal.

---

### Panel 6 — Binance REST Health (Time series, row 4, full width)

Exchange connectivity. The most actionable panel during an exchange incident.

```
Query A: rate(coinscopeai_api_requests_total{status="2xx"}[5m])
  Legend: 2xx (success)
  Color: green

Query B: rate(coinscopeai_api_requests_total{status="5xx"}[5m])
  Legend: 5xx (error)
  Color: red

Query C: histogram_quantile(0.95, rate(coinscopeai_api_latency_seconds_bucket[5m]))
  Legend: REST p95 latency (s)
  Right Y-axis: seconds
  Color: orange
```

Annotation: reference line at 2s for REST latency SLO.

---

## Part 4 — Alert-to-Action Matrix

Quick reference. Full procedures: [`../runbooks/daily-ops.md`](../runbooks/daily-ops.md).

| Alert | Severity | Auto-recovery | Operator action |
|---|---|---|---|
| `EngineDown` | CRITICAL | No | SSH → `docker compose up -d --force-recreate` |
| `CircuitBreakerOpen` | CRITICAL | No | Read `/journal` → verify breach → `POST /circuit-breaker/reset` with reason |
| `ExposureHigh` | CRITICAL | No | No new positions. Investigate sizing logic. |
| `DailyLossLimit` | CRITICAL | Gate auto-trips | Verify breaker fired. Review journal. |
| `TooManyPositions` | CRITICAL | No | Investigate position tracker bug immediately. |
| `ScanStalled` | WARN | No | Restart scan worker or engine. |
| `DailyLossWarning` | WARN | No | Reduce new position sizes. Monitor. |
| `BinanceRestErrors` | WARN | Likely | Watch 5 min. If persistent, engage kill switch. |
| `WebSocketReconnectBurst` | WARN | Usually | Monitor for stream gaps. Kill switch if gaps > 60s. |
| `ScanSlow` | WARN | Usually | Check Binance Testnet latency. No action if < 15 min. |
| `BinanceRestSlow` | WARN | Usually | Check Binance status. No action if < 15 min. |
| `RateLimitLow` | WARN | Auto (resets) | Reduce alert frequency if persistent. |

---

## Part 5 — prometheus.yml Update Required

Add to `prometheus.yml` alongside existing `scrape_configs`:

```yaml
rule_files:
  - "prometheus-alert-rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: []
        # No Alertmanager in P0 — alerts via engine's Telegram integration only.
        # Alertmanager integration is a P2 item.
```

---

## What is not in scope for P0

| Item | Phase |
|---|---|
| Alertmanager routing and silences | P2 |
| Grafana provisioning JSON (machine-readable dashboard file) | P1 — after manual validation |
| Per-symbol SLOs | P1 — once multi-symbol scanning is stable |
| Uptime SLA for `app.coinscope.ai` dashboard | P2 |
| Error budget burn-rate alerts | P2 |

---

*Last updated: 2026-05-12 | Applies to: P0 validation phase (Binance Testnet only)*
