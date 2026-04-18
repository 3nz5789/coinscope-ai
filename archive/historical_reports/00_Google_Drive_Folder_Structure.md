# CoinScopeAI — Google Drive Folder Structure

Create the following folder hierarchy in your Google Drive under a root folder named **CoinScopeAI**.

```
📁 CoinScopeAI/
│
├── 📁 01 - Engine & Config
│   ├── 01_Engine_Config_API_Reference.docx       ← Upload this
│   ├── .env.example                               ← Upload from project root
│   └── notion_sync_config.py                     ← Upload from coinscope_trading_engine/
│
├── 📁 02 - Trading Operations
│   ├── 02_Trading_Rules_Risk_Management.docx     ← Upload this
│   ├── 04_Weekly_Performance_Report_Template.docx ← Upload this
│   └── 📁 Weekly Reports/                        ← Archive weekly reports here
│
├── 📁 03 - Skills & Automation
│   ├── 05_Manus_Skills_Reference.docx            ← Upload this
│   ├── SKILL.md                                  ← Upload from market_scanner_skill/
│   └── skill_config.json                         ← Upload from market_scanner_skill/
│
├── 📁 04 - Binance Setup
│   └── 03_Binance_Testnet_Setup_Guide.docx       ← Upload this
│
├── 📁 05 - Performance & Reports
│   └── 📁 [Year-Month]/                         ← Monthly report archives
│
└── 📁 06 - Assets
    └── 📁 Coinscope Logo Files/                  ← Already in your Drive
```

## Upload Checklist

- [ ] `01_Engine_Config_API_Reference.docx`
- [ ] `02_Trading_Rules_Risk_Management.docx`
- [ ] `03_Binance_Testnet_Setup_Guide.docx`
- [ ] `04_Weekly_Performance_Report_Template.docx`
- [ ] `05_Manus_Skills_Reference.docx`
- [ ] `.env.example` (from CoinScopeAI project root)
- [ ] `SKILL.md` (from market_scanner_skill/)
- [ ] `skill_config.json` (from market_scanner_skill/)

## Sharing Recommendations

- Share the full **CoinScopeAI** folder with your Manus agent workspace (read access)
- Keep `01 - Engine & Config` restricted — contains configuration references
- Weekly reports in `02 - Trading Operations/Weekly Reports/` can be shared with collaborators
