# Documentation Generators

These scripts produce the `docs/CoinScopeAI_*.docx` and `docs/CoinScopeAI_*.pdf`
deliverables. The `*.docx` outputs are gitignored (project policy: "temporary &
generated docs"), so the scripts are the source of truth — re-run them whenever
the routing model, skill list, or voice rules change.

## Generators

- `build_routing_playbook.js` — full Skill Routing Playbook (12-section .docx).
- `build_routing_card.js` — 1-page Format Routing Quick Card (.docx, then PDF via LibreOffice).

## Usage

```bash
# From repo root, with `docx` installed locally (or globally):
cd scripts/docs
npm install docx --no-save     # or: npm install -g docx
node build_routing_playbook.js
node build_routing_card.js

# Convert the quick card .docx to .pdf
soffice --headless --convert-to pdf CoinScopeAI_FORMAT_ROUTING_CARD.docx

# Move outputs to repo docs/
mv CoinScopeAI_*.docx CoinScopeAI_*.pdf ../../docs/
```

## When to re-run

- CLAUDE.md skill table changes (add/remove/rename skill).
- New slash-command added under `.claude/commands/`.
- Risk caps revised (and reflected in CLAUDE.md).
- Phase map changes (e.g., Bybit moves from P2 to live).
