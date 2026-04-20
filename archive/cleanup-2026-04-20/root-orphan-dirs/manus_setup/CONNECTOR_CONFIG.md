# CoinScopeAI — Manus Connector Configuration

Add these connectors to your Manus project under **Project → Connectors**.

---

## Connector 1 — CoinScopeAI Engine (FastAPI)

| Field | Value |
|-------|-------|
| **Name** | CoinScopeAI Engine |
| **Type** | Custom API |
| **Base URL** | `http://localhost:8001` |
| **Auth Type** | None (local engine — no auth needed) |
| **Timeout** | 30 seconds |

### Endpoints to register:

| Name | Method | Path | Description |
|------|--------|------|-------------|
| Health Check | GET | `/health` | Confirm engine is running |
| Market Scan | GET | `/scan` | Score all pairs, return signals |
| Get Regime | GET | `/regime/{symbol}` | HMM regime for a symbol |
| Performance | GET | `/performance` | Trade performance metrics |
| Trade Journal | GET | `/journal` | Recent trade journal entries |
| Scale Position | POST | `/scale` | Kelly position sizing |
| Validate Trade | POST | `/validate` | Risk gate validation |

---

## Connector 2 — Notion API

| Field | Value |
|-------|-------|
| **Name** | Notion Trade Journal |
| **Type** | Custom API |
| **Base URL** | `https://api.notion.com/v1` |
| **Auth Type** | Bearer Token |
| **Token** | Your `NOTION_TOKEN` value from `.env` |
| **Headers** | `Notion-Version: 2022-06-28` |

### Endpoints to register:

| Name | Method | Path | Description |
|------|--------|------|-------------|
| Create Trade | POST | `/pages` | Log new trade to Trade Journal DB |
| Update Trade | PATCH | `/pages/{page_id}` | Update exit on closed trade |
| Log Signal | POST | `/pages` | Log signal to Signal Log DB |
| Query Journal | POST | `/databases/28e29aaf-938e-81eb-8c91-d166a2246520/query` | Fetch trade history |

---

## Connector 3 — Telegram Bot

| Field | Value |
|-------|-------|
| **Name** | CoinScopeAI Alerts |
| **Type** | Custom API |
| **Base URL** | `https://api.telegram.org` |
| **Auth Type** | None (token in URL path) |

### Endpoints to register:

| Name | Method | Path | Description |
|------|--------|------|-------------|
| Send Alert | POST | `/bot{TELEGRAM_BOT_TOKEN}/sendMessage` | Send signal alert to chat |

**Body template for alerts:**
```json
{
  "chat_id": "{TELEGRAM_CHAT_ID}",
  "text": "🚨 CoinScopeAI SIGNAL\nPair: {symbol}\nSignal: {direction} | Score: {score}/12\nRegime: {regime} | TF: {timeframe}",
  "parse_mode": "HTML"
}
```

---

## Knowledge Base Files to Upload

Under **Project → Knowledge Base**, upload these files from your CoinScopeAI folder:

| File | Purpose |
|------|---------|
| `MASTER_INSTRUCTIONS.md` | Agent behaviour and automation rules |
| `market_scanner_skill/SKILL.md` | Market Scanner skill spec |
| `manus_setup/skills/regime_detector/SKILL.md` | Regime Detector skill spec |
| `manus_setup/skills/position_sizer/SKILL.md` | Position Sizer skill spec |
| `manus_setup/skills/risk_gate/SKILL.md` | Risk Gate skill spec |
| `manus_setup/skills/trade_journal/SKILL.md` | Trade Journal skill spec |
| `manus_setup/skills/performance_analyzer/SKILL.md` | Performance Analyzer skill spec |
| `01_Engine_Config_API_Reference.docx` | API reference for the agent |
| `02_Trading_Rules_Risk_Management.docx` | Trading rules the agent enforces |
