// CoinScopeAI — Format Routing Quick Card (1-page companion)
// Produces CoinScopeAI_FORMAT_ROUTING_CARD.docx
// Run: node build_routing_card.js

const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, BorderStyle, WidthType, ShadingType,
  HeadingLevel, PageNumber, Header, Footer,
} = require('docx');

const border = { style: BorderStyle.SINGLE, size: 4, color: "C9CDD2" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerShading = { fill: "0F172A", type: ShadingType.CLEAR };
const altShading    = { fill: "F4F6F8", type: ShadingType.CLEAR };
const cellMargins   = { top: 50, bottom: 50, left: 100, right: 100 };

// Compact body run
function tr(text, opts = {}) {
  return new TextRun({ text, size: 18, ...opts });
}

function makeTable(columnWidths, headerCells, dataRows, headerSize = 18) {
  const totalWidth = columnWidths.reduce((a, b) => a + b, 0);
  const headerRow = new TableRow({
    tableHeader: true,
    children: headerCells.map((txt, i) => new TableCell({
      borders, margins: cellMargins, shading: headerShading,
      width: { size: columnWidths[i], type: WidthType.DXA },
      children: [new Paragraph({
        spacing: { before: 20, after: 20 },
        children: [new TextRun({ text: txt, bold: true, color: "FFFFFF", size: headerSize })],
      })],
    })),
  });
  const bodyRows = dataRows.map((row, rIdx) => new TableRow({
    children: row.map((cell, i) => {
      const text = (typeof cell === 'string') ? cell : cell.text;
      const mono = (typeof cell === 'object') && cell.mono;
      const bold = (typeof cell === 'object') && cell.bold;
      const runOpts = {
        size: 18,
        ...(mono ? { font: "Consolas", size: 17 } : {}),
        ...(bold ? { bold: true } : {}),
      };
      return new TableCell({
        borders, margins: cellMargins,
        shading: rIdx % 2 === 1 ? altShading : { fill: "FFFFFF", type: ShadingType.CLEAR },
        width: { size: columnWidths[i], type: WidthType.DXA },
        children: [new Paragraph({
          spacing: { before: 20, after: 20 },
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

const children = [];

// Title
children.push(new Paragraph({
  spacing: { before: 0, after: 40 },
  children: [new TextRun({ text: "CoinScopeAI — Format Routing Quick Card", bold: true, size: 30 })],
}));
children.push(new Paragraph({
  spacing: { before: 0, after: 120 },
  children: [new TextRun({ text: "v1, 2026-05-04 · Pair with the full Skill Routing Playbook for domain skills + workflow recipes.", color: "475569", size: 16, italics: true })],
}));

// 1. Routing table
children.push(new Paragraph({
  spacing: { before: 0, after: 60 },
  children: [new TextRun({ text: "1. Routing table — what to use when", bold: true, size: 22, color: "0F172A" })],
}));
children.push(makeTable(
  [3300, 1900, 4160],
  ["If you're doing…", "Lean on…", "Notes"],
  [
    ["Trading dashboard UI, app shell, modals, settings", { text: "frontend-design", mono: true }, "React / Next / Tailwind. Layout & UX."],
    ["Charts for PnL, drawdown, win-rate, KPIs",          { text: "chart", mono: true },           "Performance + business metrics visuals."],
    ["Reports, SOPs, incident writeups, investor docs",   { text: "docx", mono: true },            "Structured Word output with headings."],
    ["Trade logs, KPI trackers, pricing models",          { text: "xlsx", mono: true },            "Spreadsheets with formulas & tables."],
    ["Marketing site, docs portal, static pages",         { text: "website-building", mono: true },"IA, page layouts, marketing flows."],
  ]
));
children.push(new Paragraph({
  spacing: { before: 60, after: 120 },
  children: [tr("Claude can load multiple skills at once; your job is to hint which skill(s) are most relevant in line 1.", { italics: true, color: "475569" })],
}));

// 2. Prompt openers
children.push(new Paragraph({
  spacing: { before: 0, after: 40 },
  children: [new TextRun({ text: "2. Prompt openers (line 1 only — names the skill)", bold: true, size: 22, color: "0F172A" })],
}));
function opener(label, text) {
  return [
    new Paragraph({
      spacing: { before: 40, after: 0 },
      children: [tr(label, { bold: true })],
    }),
    new Paragraph({
      spacing: { before: 0, after: 40 },
      indent: { left: 240 },
      children: [tr(text, { italics: true })],
    }),
  ];
}
opener("A. Product / dashboard work", "\"Lead frontend engineer. Prefer the frontend-design skill. I'll paste React/Tailwind for [screen]. Analyze UX, propose a layout, output updated code consistent with a pro trading SaaS dashboard.\"").forEach(p => children.push(p));
opener("B. Trading analytics views",  "\"Quant UX and data-viz lead. Use the chart skill. Input: CSV/JSON of trades and equity. Output: 3–5 chart specs for the operator dashboard + 1 layout for the weekly investor report.\"").forEach(p => children.push(p));
opener("C. Reports / SOPs / incidents","\"Head of operations. Use the docx skill. Topic: [incident / weekly report / SOP]. Structure: Objective → Context → Analysis → Recommended approach → Deliverables → Next steps.\"").forEach(p => children.push(p));
opener("D. Spreadsheets and models",  "\"Data and ops analyst. Use the xlsx skill. Build a workbook for [daily PnL / symbol stats / KPIs]. Formulas, basic formatting, summary sheet with key metrics.\"").forEach(p => children.push(p));
opener("E. Marketing site, docs portal","\"Product designer. Use the website-building skill. Design a CoinScopeAI homepage (hero, trust, features, pricing, CTA). Semantic HTML + minimal CSS tokens. Serious fintech product voice.\"").forEach(p => children.push(p));

// 3. Five rules
children.push(new Paragraph({
  spacing: { before: 120, after: 40 },
  children: [new TextRun({ text: "3. Five routing rules", bold: true, size: 22, color: "0F172A" })],
}));
const rules = [
  "Name the skill explicitly in your first prompt.",
  "One primary skill per task, plus at most one helper.",
  "Describe the workflow outcome, not just \"make it prettier.\"",
  "Keep prompts short and specific — skill files hold the patterns.",
  "Reuse the same templates so routing stays consistent.",
];
rules.forEach((r, i) => {
  children.push(new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    spacing: { before: 20, after: 20 },
    children: [tr(r)],
  }));
});

// 4. Pre-session checklist
children.push(new Paragraph({
  spacing: { before: 120, after: 40 },
  children: [new TextRun({ text: "4. Pre-session checklist", bold: true, size: 22, color: "0F172A" })],
}));
children.push(makeTable(
  [4700, 4660],
  ["Question", "Routing decision"],
  [
    ["Is this UI / product?",        { text: "say: \"prefer frontend-design.\"",  mono: true }],
    ["Is this metrics / charts?",    { text: "say: \"use chart.\"",                mono: true }],
    ["Is this a formal doc?",        { text: "say: \"use docx.\"",                 mono: true }],
    ["Is this a spreadsheet?",       { text: "say: \"use xlsx.\"",                 mono: true }],
    ["Is this a website / docs?",    { text: "say: \"use website-building.\"",     mono: true }],
  ]
));
children.push(new Paragraph({
  spacing: { before: 60, after: 0 },
  children: [tr("Then 1–2 sentences of context, paste data/code, run.", { italics: true, color: "475569" })],
}));

const doc = new Document({
  creator: "Scoopy",
  title: "CoinScopeAI — Format Routing Quick Card",
  description: "1-page format-skill routing companion to the full playbook.",
  styles: {
    default: { document: { run: { font: "Arial", size: 18 } } },
  },
  numbering: {
    config: [
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 480, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        // Tight margins to fit on one page
        margin: { top: 720, right: 1080, bottom: 720, left: 1080 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        spacing: { after: 60 },
        children: [tr("CoinScopeAI · Format Routing Quick Card v1", { color: "94A3B8", size: 14 })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.LEFT,
        children: [tr("Testnet only. 30-day validation phase. No real capital. · Companion: docs/CoinScopeAI_SKILL_ROUTING.docx", { color: "94A3B8", size: 14 })],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/sleepy-laughing-gates/mnt/outputs/CoinScopeAI_FORMAT_ROUTING_CARD.docx";
  fs.writeFileSync(out, buf);
  console.log("OK wrote", out, buf.length, "bytes");
});
