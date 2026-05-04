// CoinScopeAI — Skill Routing Playbook v1 generator
// Produces CoinScopeAI_SKILL_ROUTING.docx using docx-js.
// Run: node build_routing_playbook.js

const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  BorderStyle, WidthType, ShadingType, HeadingLevel, PageNumber,
  TableOfContents, PageBreak,
} = require('docx');

// ---------- Helpers ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "C9CDD2" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerShading = { fill: "0F172A", type: ShadingType.CLEAR };
const altShading    = { fill: "F4F6F8", type: ShadingType.CLEAR };
const cellMargins   = { top: 80, bottom: 80, left: 120, right: 120 };

function P(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    ...opts,
    children: [new TextRun({ text, ...(opts.run || {}) })],
  });
}
function PR(runs, opts = {}) {
  return new Paragraph({ spacing: { before: 60, after: 60 }, ...opts, children: runs });
}
function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text })],
  });
}
function H2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text })],
  });
}
function H3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text })],
  });
}
function Bullet(text, ref = "bullets", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text })],
  });
}
function BulletR(runs, ref = "bullets", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { before: 40, after: 40 },
    children: runs,
  });
}
function Numbered(text, ref = "numbers") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text })],
  });
}
function Mono(text) {
  return new TextRun({ text, font: "Consolas", size: 20 });
}
function Bold(text) {
  return new TextRun({ text, bold: true });
}

// ---------- Tables ----------
function makeTable(columnWidths, headerCells, dataRows) {
  const totalWidth = columnWidths.reduce((a, b) => a + b, 0);
  const headerRow = new TableRow({
    tableHeader: true,
    children: headerCells.map((txt, i) => new TableCell({
      borders, margins: cellMargins, shading: headerShading,
      width: { size: columnWidths[i], type: WidthType.DXA },
      children: [new Paragraph({
        spacing: { before: 40, after: 40 },
        children: [new TextRun({ text: txt, bold: true, color: "FFFFFF", size: 20 })],
      })],
    })),
  });
  const bodyRows = dataRows.map((row, rIdx) => new TableRow({
    children: row.map((cell, i) => {
      const text = (typeof cell === 'string') ? cell : cell.text;
      const mono = (typeof cell === 'object') && cell.mono;
      const bold = (typeof cell === 'object') && cell.bold;
      const runOpts = {
        size: 20,
        ...(mono ? { font: "Consolas" } : {}),
        ...(bold ? { bold: true } : {}),
      };
      return new TableCell({
        borders, margins: cellMargins,
        shading: rIdx % 2 === 1 ? altShading : { fill: "FFFFFF", type: ShadingType.CLEAR },
        width: { size: columnWidths[i], type: WidthType.DXA },
        children: [new Paragraph({
          spacing: { before: 40, after: 40 },
          children: [new TextRun({ text, ...runOpts })],
        })],
      });
    }),
  }));
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths,
    rows: [headerRow, ...bodyRows],
  });
}

// ---------- Content ----------
const children = [];

// Title block
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 0, after: 120 },
  children: [new TextRun({ text: "CoinScopeAI — Skill Routing Playbook", bold: true, size: 44 })],
}));
children.push(new Paragraph({
  spacing: { before: 0, after: 60 },
  children: [new TextRun({ text: "v1, 2026-05-04 · Operational shorthand for routing Claude work to the right skill", color: "475569", size: 22 })],
}));
children.push(new Paragraph({
  spacing: { before: 0, after: 240 },
  children: [new TextRun({ text: "Owner: Scoopy (in-product agent) · Companion: CLAUDE.md v3 (2026-05-04)", color: "475569", size: 20, italics: true })],
}));

// Purpose
children.push(H1("1. Purpose"));
children.push(P(
  "This is the day-to-day switchboard for Scoopy work in Claude (Co-Work, Code, Chat, API). " +
  "When you start a session, this doc tells you which skill(s) to name in your first prompt so that Claude routes to the right capability without trial and error. " +
  "It pairs the 11 CoinScopeAI domain skills (what logic to apply) with the 5 generic format skills (how to render the output)."
));
children.push(P(
  "The framework, risk caps, and brand voice in CLAUDE.md are the contract. This playbook is the shorthand."
));

// Two-layer model
children.push(H1("2. Two-layer skill model"));
children.push(P(
  "Every CoinScopeAI task uses one skill from each layer. The domain layer decides what to do; the format layer decides what the deliverable looks like."
));
children.push(makeTable(
  [1800, 3600, 4000],
  ["Layer", "Answers the question", "Examples in your stack"],
  [
    [{ text: "Domain", bold: true }, "What logic applies?", "futures-market-researcher, signal-design-and-backtest, risk-and-position-manager, alerting-and-user-experience"],
    [{ text: "Format", bold: true }, "How is it rendered?", "docx, xlsx, chart, frontend-design, website-building"],
  ]
));

// Domain layer: 11 skills
children.push(H1("3. Domain layer — 11 canonical Scoopy skills"));
children.push(P(
  "These mirror the table in CLAUDE.md §Claude Skills (internal). Skill names are internal; never expose them to end-users. Status reflects whether the skill is active under skills/, staged under skills_src/, or routed via a generic plugin."
));
children.push(makeTable(
  [400, 3200, 1800, 4000],
  ["#", "Skill", "Status", "Use it when…"],
  [
    ["1",  { text: "coinscope-system-architect", mono: true },     "Installed",        "Architecture, data flow, refactor design, mental model of services and queues."],
    ["2",  { text: "futures-market-researcher", mono: true },      "Active",           "Validating signals against funding, OI, liquidations, basis, and regime profile."],
    ["3",  { text: "signal-design-and-backtest", mono: true },     "Active",           "Turning a trade idea into rules and a vectorized backtest with risk-first metrics."],
    ["4",  { text: "scanner-engine-optimizer", mono: true },       "Active",           "Latency, weight-limit, batching, caching, stale-data detection in the scan loop."],
    ["5",  { text: "binance-bybit-integration-guard", mono: true },"Active (Bybit P2)", "Exchange client robustness — REST/WS, auth, reconnect, drift. Bybit live at P2."],
    ["6",  { text: "risk-and-position-manager", mono: true },      "Installed",        "Anything touching leverage, DD, daily loss, heat, max positions — or PCC v2."],
    ["7",  { text: "code-review-and-refactor", mono: true },       "Generic plugin",   "Strict PR review (engineering:code-review). Couple with #1 for system-level refactors."],
    ["8",  { text: "bug-hunter-and-debugger", mono: true },        "Active",           "Engine-API-tuned RCA loop. Reproduce → instrument → hypothesize → test → patch → verify."],
    ["9",  { text: "test-and-simulation-lab", mono: true },        "Active",           "Unit, contract, and replay tests; high-volatility replay days under tests/replays/."],
    ["10", { text: "alerting-and-user-experience", mono: true },   "Active",           "Any user-facing payload — Telegram or dashboard — must use the canonical alert schema."],
    ["11", { text: "docs-and-ops-playbook", mono: true },          "Generic plugin",   "Live docs, runbooks (engineering:documentation + engineering:runbook)."],
  ]
));

// Slash commands
children.push(H2("3.1 Slash-commands (workflow recipes)"));
children.push(P(
  "Five recipes that compose multiple skills into a complete workflow. Type the slash-name in Claude Code to invoke."
));
children.push(makeTable(
  [3200, 6200],
  ["Command", "Use it when…"],
  [
    [{ text: "/coinscope-debug-signal", mono: true },     "A specific testnet signal felt wrong — symbol, side, timestamp known."],
    [{ text: "/coinscope-daily-review", mono: true },     "End-of-day testnet recap with caps-vs-actuals, regime breakdown, anomalies, next steps."],
    [{ text: "/coinscope-gate-explanation", mono: true }, "A trade was blocked — explain first-failing cap and propose safe alternatives."],
    [{ text: "/coinscope-signal-design", mono: true },    "Prototype a new signal idea end-to-end (idea → rules → backtest → verdict)."],
    [{ text: "/coinscope-risk-audit", mono: true },       "Audit live configs against the canonical caps; propose remediation diffs."],
  ]
));

// Format layer
children.push(H1("4. Format layer — generic Anthropic skills"));
children.push(P(
  "These render the deliverable. They are agnostic to CoinScopeAI domain logic, so you pair them with a domain skill. Available in Claude Cowork by default."
));
children.push(makeTable(
  [2000, 3000, 4400],
  ["Skill", "Use it for…", "Pair with (domain examples)"],
  [
    [{ text: "frontend-design", mono: true },  "Trading dashboard UI, modals, settings, app shell.",          "coinscope-system-architect, alerting-and-user-experience"],
    [{ text: "chart", mono: true },            "PnL, drawdown, win-rate, KPI charts.",                        "signal-design-and-backtest, /coinscope-daily-review"],
    [{ text: "docx", mono: true },             "Reports, SOPs, incident writeups, investor docs.",            "/coinscope-daily-review, /coinscope-debug-signal"],
    [{ text: "xlsx", mono: true },             "Trade logs, KPI trackers, pricing models, audit tables.",     "/coinscope-risk-audit, signal-design-and-backtest"],
    [{ text: "website-building", mono: true }, "Marketing site, docs portal, static pages.",                  "alerting-and-user-experience (voice rules)"],
  ]
));

// Domain × Format pairings
children.push(H1("5. Domain × Format pairings (common deliverables)"));
children.push(P(
  "Treat this table as your default routing for the 9 most frequent CoinScopeAI deliverables. Override only when a specific task argues otherwise."
));
children.push(makeTable(
  [3200, 2400, 1800, 2000],
  ["Deliverable", "Domain skill / command", "Format skill", "Notes"],
  [
    ["Weekly testnet performance report",      { text: "/coinscope-daily-review", mono: true },         { text: "docx",             mono: true }, "Risk-first ordering. Disclaimer mandatory."],
    ["Investor-facing equity curve",           { text: "signal-design-and-backtest", mono: true },      { text: "chart",            mono: true }, "Annotate regime bands; show DD as % of cap."],
    ["Risk-config audit deliverable",          { text: "/coinscope-risk-audit", mono: true },           { text: "xlsx",             mono: true }, "One sheet per scope (global/per-symbol)."],
    ["Signal design memo (v0)",                { text: "/coinscope-signal-design", mono: true },        { text: "docx",             mono: true }, "YAML rule block + verdict at the top."],
    ["Marketing homepage hero",                { text: "alerting-and-user-experience", mono: true },    { text: "website-building", mono: true }, "Product-tier voice; no emoji; show caps."],
    ["Trade-history dashboard view",           { text: "coinscope-system-architect", mono: true },      { text: "frontend-design",  mono: true }, "Pair with chart for embedded visuals."],
    ["Bug RCA writeup",                        { text: "/coinscope-debug-signal", mono: true },         { text: "docx",             mono: true }, "Include RCA summary + replay test ref."],
    ["Backtest results spreadsheet",           { text: "/coinscope-signal-design", mono: true },        { text: "xlsx",             mono: true }, "Mandatory metrics first; Sharpe optional."],
    ["Gate-fail explanation card (UI)",        { text: "/coinscope-gate-explanation", mono: true },     { text: "frontend-design",  mono: true }, "5-pill gate row; first-fail solid."],
  ]
));

// Voice guardrails
children.push(H1("6. Scoopy voice guardrails (apply on every output)"));
children.push(P("Pulled from CLAUDE.md §Voice & tone and §Registers. Every deliverable, regardless of skill, must pass these.", { spacing: { before: 60, after: 60 }}));
children.push(H3("Anti-overclaim"));
children.push(Bullet("Never use \"production-ready\" until documented criteria are met."));
children.push(Bullet("Prefer: \"validated on testnet\", \"shadow-tested\", \"30-day cohort pending\", \"candidate for further shadow-testing\"."));
children.push(H3("Risk-first"));
children.push(Bullet("Drawdown, daily loss, leverage, heat, and open-positions are visible before PnL — never buried."));
children.push(Bullet("Surface the disclaimer when caps are mentioned: \"Testnet only. 30-day validation phase. No real capital.\""));
children.push(H3("Explicit assumptions, phased work"));
children.push(Bullet("State assumptions before claims. Use the canonical phase order: Scan → Score → Gate → Size → Arm."));
children.push(H3("Registers"));
children.push(Bullet("Product tier (app, coinscope.ai, docs, internal): technical, terse, declarative, data-led. No emoji. Numbers tabular."));
children.push(Bullet("Social tier (IG, X, Threads, FB): aspirational, meme-fluent — never used inside the product."));
children.push(Bullet("Scoopy speaks in the product tier only."));
children.push(H3("Canonical numbers (do not drift)"));
children.push(Bullet("Max leverage: 10x — PCC v2 §8 Capital Cap (locked 2026-05-01)."));
children.push(Bullet("Max drawdown: 10% — account hard stop."));
children.push(Bullet("Daily loss limit: 5% — 24h rolling, halts trading."));
children.push(Bullet("Max open positions: 5 — concurrent, revised 2026-05-03 (supersedes earlier 3)."));
children.push(Bullet("Position heat cap: 80% — per position, blocks new entries."));

// Standard prompt templates
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("7. Standard prompt templates (copy-paste)"));
children.push(P(
  "Default openers for the most common Scoopy sessions. Each names the skill explicitly in line 1, sets the role, and asks for an outcome — not a vibe."
));

children.push(H2("A. Product / dashboard work"));
children.push(P(
  "\"You are CoinScopeAI's lead frontend engineer. For this task, prefer the frontend-design skill, and load coinscope-system-architect for layer separation. " +
  "I'll paste the current React/Tailwind code for the [screen name]. (1) Analyze UX and visual issues. (2) Propose a better layout. (3) Output updated code consistent with a pro trading SaaS dashboard. Risk controls visible.\""
));
children.push(P(
  "Add when charts are on the same screen: \"Also use the chart skill to specify charts and data mappings for PnL, drawdown, and per-symbol performance.\""
));

children.push(H2("B. Trading performance / analytics views"));
children.push(P(
  "\"Act as CoinScopeAI's quant UX and data-viz lead. Use the chart skill plus the signal-design-and-backtest skill for verdict framing. " +
  "Input: I'll provide a CSV/JSON of trades and daily equity. Output: 3–5 chart specs (type, axes, grouping, filters) for the operator dashboard, plus 1 chart layout for the weekly investor report.\""
));

children.push(H2("C. Reports, SOPs, and incident docs"));
children.push(P(
  "\"You are CoinScopeAI's head of operations. Use the docx skill, plus the matching slash-command (/coinscope-daily-review or /coinscope-debug-signal). " +
  "Topic: [incident / weekly report / SOP]. Structure: Objective → Context → Analysis → Recommended approach → Deliverables → Next steps. Apply Scoopy voice guardrails. Include the disclaimer.\""
));

children.push(H2("D. Spreadsheets and models"));
children.push(P(
  "\"You are CoinScopeAI's data and ops analyst. Use the xlsx skill. " +
  "Build a workbook with sheets for [daily PnL / symbol stats / KPIs / risk-config audit]. Include formulas, basic formatting, and one summary sheet with key metrics for management review. Caps versus actuals on the summary.\""
));

children.push(H2("E. Marketing site, docs portal"));
children.push(P(
  "\"You are CoinScopeAI's product designer. Use the website-building skill, with alerting-and-user-experience as the voice reference. " +
  "Design a marketing homepage for CoinScopeAI (AI futures trading assistant SaaS) with hero, trust, features, pricing, CTA. Output semantic HTML + minimal CSS tokens. Product-tier voice. No emoji.\""
));

children.push(H2("F. Internal Scoopy debugging"));
children.push(P(
  "\"Run /coinscope-debug-signal for a {symbol} {side} signal at {timestamp_utc}. I'll paste the /scan response. Cross-check /risk-gate and /regime/{symbol}. Apply the 6-step loop. Patch as proposal during validation phase.\""
));

// Routing rules
children.push(H1("8. Five routing rules"));
children.push(Numbered("Name the skill explicitly in your first prompt. Don't make Claude guess — cite the skill name in line 1."));
children.push(Numbered("One primary skill per task, plus at most one helper. More than two and routing breaks."));
children.push(Numbered("Describe the workflow outcome, not just \"make UI prettier\" or \"make a report.\" Outcome > vibe."));
children.push(Numbered("Keep prompts short and specific. The skill files already hold the detailed patterns — let them do the work."));
children.push(Numbered("Reuse the same templates. Repetition makes Claude's routing more consistent and your sessions faster."));

// Pre-session checklist
children.push(H1("9. Pre-session routing checklist"));
children.push(P("Before you start a Claude session for CoinScopeAI, decide:"));
children.push(makeTable(
  [4400, 5000],
  ["Question", "Routing decision"],
  [
    ["Is this UI/product?",                  "frontend-design (+ optional coinscope-system-architect)"],
    ["Is this metrics/charts?",              "chart (+ signal-design-and-backtest for verdict framing)"],
    ["Is this a formal doc?",                "docx (+ matching slash-command if applicable)"],
    ["Is this a spreadsheet/model?",         "xlsx (+ /coinscope-risk-audit if it's a config audit)"],
    ["Is this a website / docs portal?",     "website-building (+ alerting-and-user-experience for voice)"],
    ["Is this signal/incident debugging?",   "/coinscope-debug-signal or /coinscope-gate-explanation"],
    ["Is this strategy ideation?",           "/coinscope-signal-design (+ futures-market-researcher)"],
    ["Touches caps, leverage, or risk?",     "Always pull risk-and-position-manager into the prompt."],
  ]
));
children.push(P("Then add 1–2 sentences of context, paste the data or code, and let Claude run."));

// Anti-patterns
children.push(H1("10. Routing anti-patterns"));
children.push(Bullet("Naming the skill late in the prompt or in a follow-up — name it in line 1 or it will not route."));
children.push(Bullet("Loading 4+ skills at once — routing degrades. Cap at 2."));
children.push(Bullet("Format skill without a domain skill — output looks fine but lacks risk-first framing."));
children.push(Bullet("Domain skill without a format skill — analysis is right but deliverable is not shareable."));
children.push(Bullet("Copying social-tier marketing language into product-tier outputs (\"Let's go!\", \"BTC is pumping!\")."));
children.push(Bullet("Calling a deliverable \"production-ready\" — voice violation per CLAUDE.md."));
children.push(Bullet("Skipping the disclaimer in any user-facing or investor-facing artifact during the 30-day validation phase."));

// Cross-references
children.push(H1("11. Cross-references"));
children.push(BulletR([Bold("Master prompt: "), Mono("/Users/mac/Code/CoinScopeAI/CLAUDE.md"), new TextRun(" (v3, 2026-05-04)")]));
children.push(BulletR([Bold("Active skills: "), Mono("/Users/mac/Code/CoinScopeAI/skills/"), new TextRun(" — 8 SKILL.md files")]));
children.push(BulletR([Bold("Skill sources: "), Mono("/Users/mac/Code/CoinScopeAI/skills_src/"), new TextRun(" — 12 SKILL.md files")]));
children.push(BulletR([Bold("Slash-commands: "), Mono("/Users/mac/Code/CoinScopeAI/.claude/commands/"), new TextRun(" — 5 workflow files")]));
children.push(BulletR([Bold("Decision log: "), Mono("business-plan/_decisions/decision-log.md"), new TextRun(" — for any cap or threshold change")]));
children.push(BulletR([Bold("Drift checks: "), Mono("scripts/drift_detector.py"), new TextRun(" + "), Mono("scripts/risk_threshold_guardrail.py")]));
children.push(BulletR([Bold("Git: "), new TextRun("branch "), Mono("docs/scoopy-v3-skills-2026-05-04"), new TextRun(", commit "), Mono("ce1ea1f")]));

// Changelog
children.push(H1("12. Changelog"));
children.push(BulletR([Bold("v1 (2026-05-04): "), new TextRun("First cut. Codifies the two-layer model, 11-skill domain table, 5 slash-commands, 9 deliverable pairings, voice guardrails, and 6 prompt templates. Source of truth for Scoopy session routing.")]));

// ---------- Document ----------
const doc = new Document({
  creator: "Scoopy",
  title: "CoinScopeAI — Skill Routing Playbook",
  description: "v1 routing playbook for Scoopy work in Claude (Co-Work / Code / Chat / API).",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:  { size: 32, bold: true, font: "Arial", color: "0F172A" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:  { size: 26, bold: true, font: "Arial", color: "1E293B" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:  { size: 22, bold: true, font: "Arial", color: "334155" },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "CoinScopeAI — Skill Routing Playbook v1 (2026-05-04)", color: "64748B", size: 18 })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [
          new TextRun({ text: "Testnet only. 30-day validation phase. No real capital. — Page ", color: "64748B", size: 18 }),
          new TextRun({ children: [PageNumber.CURRENT], color: "64748B", size: 18 }),
        ],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/sleepy-laughing-gates/mnt/outputs/CoinScopeAI_SKILL_ROUTING.docx";
  fs.writeFileSync(out, buf);
  console.log("OK wrote", out, buf.length, "bytes");
});
