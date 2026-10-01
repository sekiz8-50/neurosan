const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "TecqGroep";
p.title = "VIF automation — business case";

const W = 13.33, H = 7.5, M = 0.65;
const ORANGE = "FF7D2F", DARK = "16181D", INK = "1C1C1C", MUTED = "6E6E70",
      LIGHT = "F4F3F1", WHITE = "FFFFFF", LINE = "DEDCD7";
const DISP = "Arial Black", HEAD = "Arial", BODY = "Calibri";

function shadow() { return { type: "outer", color: "000000", blur: 7, offset: 2, angle: 135, opacity: 0.10 }; }

function bracketPair(s, x, y, w, h, color, t, arm) {
  const R = p.shapes.RECTANGLE, f = { fill: { color: color } };
  s.addShape(R, Object.assign({ x: x, y: y, w: t, h: h }, f));
  s.addShape(R, Object.assign({ x: x, y: y, w: arm, h: t }, f));
  s.addShape(R, Object.assign({ x: x, y: y + h - t, w: arm, h: t }, f));
  s.addShape(R, Object.assign({ x: x + w - t, y: y, w: t, h: h }, f));
  s.addShape(R, Object.assign({ x: x + w - arm, y: y, w: arm, h: t }, f));
  s.addShape(R, Object.assign({ x: x + w - arm, y: y + h - t, w: arm, h: t }, f));
}

function kicker(s, text, x, y, color) {
  s.addText(text.toUpperCase(), { x: x, y: y, w: 8, h: 0.3, fontFace: HEAD, bold: true,
    fontSize: 12, color: color || ORANGE, charSpacing: 3, margin: 0 });
}

function title(s, text, x, y, color) {
  s.addText(text, { x: x, y: y, w: W - 2 * M, h: 0.9, fontFace: HEAD, bold: true,
    fontSize: 32, color: color || INK, margin: 0 });
}

function card(s, x, y, w, h, fill) {
  s.addShape(p.shapes.RECTANGLE, { x: x, y: y, w: w, h: h, fill: { color: fill || WHITE },
    line: { color: LINE, width: 0.75 }, shadow: shadow() });
}

// ---------- Slide 1 — TITLE ----------
let s = p.addSlide(); s.background = { color: DARK };
bracketPair(s, 9.7, 1.5, 2.9, 4.4, ORANGE, 0.06, 0.55);
s.addText("ENGINEER", { x: 9.7, y: 4.5, w: 2.9, h: 0.6, align: "center", fontFace: DISP, fontSize: 24, color: WHITE, margin: 0 });
s.addText("JOIN THE FUTURE TECHFORCE", { x: 9.7, y: 5.15, w: 2.9, h: 0.3, align: "center", fontFace: HEAD, bold: true, fontSize: 9, color: ORANGE, charSpacing: 2, margin: 0 });
kicker(s, "TecqGroep · Maintec & Tecforce", M, 1.5);
s.addText("VIF automation", { x: M, y: 2.0, w: 9, h: 1.2, fontFace: DISP, fontSize: 52, color: WHITE, margin: 0 });
s.addText("From vacancy intake to live campaign — fully automatic.", { x: M, y: 3.35, w: 8.6, h: 0.7, fontFace: HEAD, fontSize: 19, color: ORANGE, margin: 0 });
s.addText("One upload by sales. The brain writes, visualises, records and stages the campaign. Marketing approves with one click — and the vacancy is live.", { x: M, y: 4.15, w: 8.4, h: 1.1, fontFace: BODY, fontSize: 14.5, color: "C9C8C5", lineSpacing: 22, margin: 0 });
s.addText("Business case for the board · June 2026", { x: M, y: 6.6, w: 8, h: 0.3, fontFace: BODY, fontSize: 12, color: "8A8A8C", margin: 0 });

// ---------- Slide 2 — THE PROBLEM ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "The current situation", M, 0.55);
title(s, "Today: manual work, waiting time and error-prone", M, 0.9);
const pains = [
  ["Fragmented process", "Sales -> recruiter -> marketing, with handovers and waiting time at every step."],
  ["A lot of manual typing", "Vacancy text, SEO, image, Tigris entry and the Meta campaign - all by hand."],
  ["Slow turnaround", "A vacancy only goes live after days; meanwhile the market moves on."],
  ["Variable quality", "Text, SEO and branding depend on whoever happens to pick it up."],
];
let py = 2.1;
pains.forEach(function (it) {
  card(s, M, py, 6.7, 1.0, LIGHT);
  s.addShape(p.shapes.RECTANGLE, { x: M, y: py, w: 0.08, h: 1.0, fill: { color: ORANGE } });
  s.addText(it[0], { x: M + 0.3, y: py + 0.13, w: 6.2, h: 0.35, fontFace: HEAD, bold: true, fontSize: 15, color: INK, margin: 0 });
  s.addText(it[1], { x: M + 0.3, y: py + 0.48, w: 6.2, h: 0.45, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0 });
  py += 1.15;
});
function stat(s, x, y, big, lbl, sub) {
  s.addText(big, { x: x, y: y, w: 4.6, h: 1.0, fontFace: DISP, fontSize: 50, color: ORANGE, margin: 0 });
  s.addText(lbl, { x: x, y: y + 1.0, w: 4.6, h: 0.4, fontFace: HEAD, bold: true, fontSize: 16, color: INK, margin: 0 });
  if (sub) s.addText(sub, { x: x, y: y + 1.4, w: 4.6, h: 0.4, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0 });
}
stat(s, 8.0, 2.2, "~ 2.8 hrs", "manual work per vacancy", "text · SEO · image · entry · campaign");
stat(s, 8.0, 4.5, "days", "turnaround to live", "every day of delay = missed candidates");

// ---------- Slide 3 — THE SOLUTION ----------
s = p.addSlide(); s.background = { color: DARK };
kicker(s, "The solution", M, 0.6);
title(s, "One upload - the rest happens automatically", M, 0.95, WHITE);
const flow = [
  ["1", "Upload", "Sales posts the VIF at maintec.nl/vif"],
  ["2", "Automatic", "Text, image, Tigris & Meta campaign"],
  ["3", "Approve", "Marketing approves with one click"],
  ["4", "Live", "Vacancy + lead campaign online"],
];
let fx = M, fw = 2.78, gap = 0.32;
flow.forEach(function (it, i) {
  const x = fx + i * (fw + gap);
  s.addShape(p.shapes.RECTANGLE, { x: x, y: 2.7, w: fw, h: 2.4, fill: { color: "1F222A" }, line: { color: "2E323C", width: 1 } });
  s.addShape(p.shapes.OVAL, { x: x + 0.3, y: 3.0, w: 0.7, h: 0.7, fill: { color: ORANGE } });
  s.addText(it[0], { x: x + 0.3, y: 3.0, w: 0.7, h: 0.7, align: "center", valign: "middle", fontFace: DISP, fontSize: 20, color: DARK, margin: 0 });
  s.addText(it[1], { x: x + 0.3, y: 3.95, w: fw - 0.6, h: 0.45, fontFace: HEAD, bold: true, fontSize: 18, color: WHITE, margin: 0 });
  s.addText(it[2], { x: x + 0.3, y: 4.4, w: fw - 0.55, h: 0.6, fontFace: BODY, fontSize: 12.5, color: "B9B8B6", margin: 0 });
  if (i < flow.length - 1) s.addText(">", { x: x + fw - 0.02, y: 3.6, w: gap, h: 0.5, align: "center", fontFace: HEAD, bold: true, fontSize: 20, color: ORANGE, margin: 0 });
});
s.addText("The recruiter spends their time on candidates again - not on data entry.", { x: M, y: 5.7, w: 12, h: 0.5, fontFace: BODY, italic: true, fontSize: 15, color: "C9C8C5", margin: 0 });

// ---------- Slide 4 — HOW IT WORKS ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "Under the hood", M, 0.55);
title(s, "How it works: the pipeline", M, 0.9);
const steps = [
  ["1", "VIF upload", "Sales uploads the Word/PDF intake form."],
  ["2", "Neuro San", "Multi-agent brain reads, validates and writes."],
  ["3", "Image", "On-brand appealing image, automatically."],
  ["4", "Tigris", "Complete vacancy record in Salesforce."],
  ["5", "Meta campaign", "Lead campaign with form staged."],
  ["6", "Live + tracking", "Online after approval, leads traceable."],
];
const lineY = 2.65, n = steps.length, sw = (W - 2 * M) / n;
s.addShape(p.shapes.LINE, { x: M + sw / 2, y: lineY, w: (W - 2 * M) - sw, h: 0, line: { color: LINE, width: 2 } });
steps.forEach(function (it, i) {
  const cx = M + sw * i + sw / 2;
  s.addShape(p.shapes.OVAL, { x: cx - 0.42, y: lineY - 0.42, w: 0.84, h: 0.84, fill: { color: ORANGE }, line: { color: WHITE, width: 3 } });
  s.addText(it[0], { x: cx - 0.42, y: lineY - 0.42, w: 0.84, h: 0.84, align: "center", valign: "middle", fontFace: DISP, fontSize: 22, color: WHITE, margin: 0 });
  s.addText(it[1], { x: cx - sw / 2 + 0.1, y: lineY + 0.7, w: sw - 0.2, h: 0.4, align: "center", fontFace: HEAD, bold: true, fontSize: 14, color: INK, margin: 0 });
  s.addText(it[2], { x: cx - sw / 2 + 0.12, y: lineY + 1.1, w: sw - 0.24, h: 0.9, align: "center", fontFace: BODY, fontSize: 11.5, color: MUTED, margin: 0 });
});
card(s, M, 5.6, W - 2 * M, 1.1, LIGHT);
s.addText([
  { text: "Roles:  ", options: { bold: true, color: INK } },
  { text: "Neuro San is the ", options: { color: MUTED } },
  { text: "brain", options: { bold: true, color: ORANGE } },
  { text: " (validating, writing, optimising); the automation are the ", options: { color: MUTED } },
  { text: "hands", options: { bold: true, color: ORANGE } },
  { text: " (image, Tigris, Meta, mail). One approval remains as the human check.", options: { color: MUTED } },
], { x: M + 0.3, y: 5.85, w: W - 2 * M - 0.6, h: 0.6, fontFace: BODY, fontSize: 13.5, valign: "middle", margin: 0 });

// ---------- Slide 5 — THE BRAIN ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "The brain", M, 0.55);
title(s, "A team of collaborating AI specialists", M, 0.9);
const agents = [
  ["Intake & validation", "Reads the VIF and checks completeness."],
  ["GDPR / privacy", "Keeps personal data out of public text."],
  ["Copywriter", "Writes appealing, on-brand vacancy text."],
  ["SEO specialist", "Keywords, meta titles and findability."],
  ["GEO / LLM", "Optimises for AI search engines + FAQ."],
  ["Brand guardian", "Guards branding, tone and compliance."],
  ["Campaign strategist", "Meta audience and ad variants."],
  ["Handoff package", "Bundles everything into one executable brief."],
];
const gx = M, gw = 2.92, ggap = 0.26, gh = 1.55;
agents.forEach(function (it, i) {
  const col = i % 4, row = Math.floor(i / 4);
  const x = gx + col * (gw + ggap), y = 2.15 + row * (gh + 0.3);
  card(s, x, y, gw, gh, WHITE);
  s.addShape(p.shapes.RECTANGLE, { x: x, y: y, w: gw, h: 0.09, fill: { color: ORANGE } });
  s.addText(it[0], { x: x + 0.22, y: y + 0.28, w: gw - 0.44, h: 0.55, fontFace: HEAD, bold: true, fontSize: 14.5, color: INK, margin: 0 });
  s.addText(it[1], { x: x + 0.22, y: y + 0.82, w: gw - 0.44, h: 0.65, fontFace: BODY, fontSize: 11.8, color: MUTED, lineSpacing: 15, margin: 0 });
});

// ---------- Slide 6 — WHAT IT DELIVERS ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "The result", M, 0.55);
title(s, "What the tooling delivers per vacancy", M, 0.9);
let bx = M, by = 2.1, bw = 5.9, bh = 2.2;
card(s, bx, by, bw, bh, WHITE);
s.addText("Professional vacancy text", { x: bx + 0.25, y: by + 0.18, w: bw - 0.5, h: 0.4, fontFace: HEAD, bold: true, fontSize: 14, color: ORANGE, margin: 0 });
["Introduction - catchy opening", "What will you do? - clear tasks", "What do we expect from you? - requirements", "What can you expect from us? - conditions", "Where will you work? - team & Maintec"].forEach(function (t, i) {
  s.addText(t, { x: bx + 0.25, y: by + 0.62 + i * 0.3, w: bw - 0.5, h: 0.3, fontFace: BODY, fontSize: 12, color: INK, bullet: { code: "2013" }, margin: 0 });
});
bx = M + bw + 0.3; bw = 5.9;
s.addShape(p.shapes.RECTANGLE, { x: bx, y: by, w: bw, h: bh, fill: { color: DARK }, line: { color: LINE, width: 0.75 }, shadow: shadow() });
s.addText("On-brand appealing image", { x: bx + 0.25, y: by + 0.18, w: bw - 0.5, h: 0.4, fontFace: HEAD, bold: true, fontSize: 14, color: ORANGE, margin: 0 });
bracketPair(s, bx + 0.6, by + 0.75, 4.7, 1.05, ORANGE, 0.045, 0.45);
s.addText("ELECTRICAL SERVICE ENGINEER", { x: bx + 0.7, y: by + 1.0, w: 4.5, h: 0.55, align: "center", valign: "middle", fontFace: DISP, fontSize: 14, color: WHITE, margin: 0 });
s.addText("JOIN THE FUTURE TECHFORCE", { x: bx + 0.6, y: by + 1.82, w: 4.7, h: 0.3, align: "center", fontFace: HEAD, bold: true, fontSize: 9, color: ORANGE, charSpacing: 2, margin: 0 });
by = 4.55; bh = 2.0;
bx = M; bw = 5.9;
card(s, bx, by, bw, bh, LIGHT);
s.addText("Complete Tigris record", { x: bx + 0.25, y: by + 0.18, w: bw - 0.5, h: 0.4, fontFace: HEAD, bold: true, fontSize: 14, color: ORANGE, margin: 0 });
const fields = [["Job title", "Electrical Service Eng."], ["Salary", "€ 2,700 - € 3,300"], ["City / province", "Barendrecht · South Holland"], ["Sector · experience", "Engineering · Mid-level"]];
fields.forEach(function (f, i) {
  const yy = by + 0.62 + i * 0.33;
  s.addText(f[0], { x: bx + 0.25, y: yy, w: 2.7, h: 0.3, fontFace: BODY, fontSize: 12, color: MUTED, margin: 0 });
  s.addText(f[1], { x: bx + 2.95, y: yy, w: bw - 3.2, h: 0.3, fontFace: BODY, bold: true, fontSize: 12, color: INK, align: "right", margin: 0 });
});
bx = M + bw + 0.3;
card(s, bx, by, bw, bh, LIGHT);
s.addText("Meta lead campaign", { x: bx + 0.25, y: by + 0.18, w: bw - 0.5, h: 0.4, fontFace: HEAD, bold: true, fontSize: 14, color: ORANGE, margin: 0 });
["Campaign + ad variants (PAUSED)", "Instant Form for direct application", "App Id tracking: lead <-> vacancy", "Activates only after your approval"].forEach(function (t, i) {
  s.addText(t, { x: bx + 0.25, y: by + 0.62 + i * 0.32, w: bw - 0.5, h: 0.3, fontFace: BODY, fontSize: 12, color: INK, bullet: { code: "2013" }, margin: 0 });
});

// ---------- Slide 7 — THIS ALREADY WORKS ----------
s = p.addSlide(); s.background = { color: DARK };
kicker(s, "Status", M, 0.6);
title(s, "Not a prototype - this is already running", M, 0.95, WHITE);
const live = [
  "Neuro San network connected (collaborating agents)",
  "Vacancy written live to Tigris / Salesforce",
  "Image generation + Maintec branding overlay",
  "Meta lead campaign working (TOS block solved)",
  "Approval mail with one-click publication",
  "Full chain tested end-to-end on Render",
];
live.forEach(function (t, i) {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.2, y = 2.4 + row * 1.1;
  s.addShape(p.shapes.OVAL, { x: x, y: y, w: 0.5, h: 0.5, fill: { color: ORANGE } });
  s.addText("v", { x: x, y: y, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: HEAD, bold: true, fontSize: 18, color: DARK, margin: 0 });
  s.addText(t, { x: x + 0.7, y: y - 0.05, w: 5.3, h: 0.6, valign: "middle", fontFace: BODY, fontSize: 14.5, color: WHITE, margin: 0 });
});
s.addText("What remains: further development (recruiter sourcing, own photo library, direct website integration).", { x: M, y: 6.4, w: 12, h: 0.5, fontFace: BODY, italic: true, fontSize: 13, color: "B9B8B6", margin: 0 });

// ---------- Slide 8 — THE ROI ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "The business case", M, 0.5);
title(s, "The ROI", M, 0.85);
const rois = [["€ 71,000", "saved per year"], ["€ 5,900", "per month"], ["110 hrs", "freed per month"], ["0.8 FTE", "freed up"]];
const rw = 2.92, rgap = 0.26;
rois.forEach(function (it, i) {
  const x = M + i * (rw + rgap);
  s.addShape(p.shapes.RECTANGLE, { x: x, y: 1.85, w: rw, h: 1.5, fill: { color: i === 0 ? ORANGE : LIGHT } });
  s.addText(it[0], { x: x + 0.1, y: 2.05, w: rw - 0.2, h: 0.7, align: "center", fontFace: DISP, fontSize: 28, color: i === 0 ? WHITE : INK, margin: 0 });
  s.addText(it[1], { x: x + 0.1, y: 2.75, w: rw - 0.2, h: 0.45, align: "center", fontFace: BODY, fontSize: 13, color: i === 0 ? "FFE7D8" : MUTED, margin: 0 });
});
s.addText("Time per vacancy", { x: M, y: 3.7, w: 6, h: 0.4, fontFace: HEAD, bold: true, fontSize: 15, color: INK, margin: 0 });
s.addChart(p.charts.BAR, [{ name: "Minutes", labels: ["Manual", "Automated"], values: [170, 5] }], {
  x: M, y: 4.1, w: 6.3, h: 2.9, barDir: "bar", chartColors: [ORANGE],
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: INK, dataLabelFontFace: HEAD, dataLabelFontSize: 13, dataLabelFontBold: true,
  catAxisLabelColor: INK, catAxisLabelFontSize: 13, catAxisLabelFontBold: true, valAxisHidden: true, valGridLine: { style: "none" },
  showLegend: false, barGapWidthPct: 60, chartArea: { fill: { color: "FFFFFF" } },
});
let ex = 7.5;
card(s, ex, 4.1, W - M - ex, 2.9, LIGHT);
s.addText("How it adds up", { x: ex + 0.3, y: 4.3, w: 4.8, h: 0.4, fontFace: HEAD, bold: true, fontSize: 15, color: ORANGE, margin: 0 });
[
  ["170 min manual work", "text 45 · SEO 15 · image 30 · entry 20 · campaign 40 · coordination 20"],
  ["becomes ~5 min", "only reviewing and approving"],
  ["≈ € 149 net saved", "per vacancy, after API and review costs"],
].forEach(function (it, i) {
  const yy = 4.75 + i * 0.7;
  s.addText(it[0], { x: ex + 0.3, y: yy, w: W - M - ex - 0.6, h: 0.32, fontFace: HEAD, bold: true, fontSize: 14, color: INK, margin: 0 });
  s.addText(it[1], { x: ex + 0.3, y: yy + 0.3, w: W - M - ex - 0.6, h: 0.4, fontFace: BODY, fontSize: 11.5, color: MUTED, margin: 0 });
});
s.addText("Assumption: 40 vacancies/month (Maintec + Tecforce) · € 55/hr all-in. Adjust in the interactive calculator.", { x: M, y: 7.05, w: 12, h: 0.35, fontFace: BODY, italic: true, fontSize: 11, color: MUTED, margin: 0 });

// ---------- Slide 9 — BROADER VALUE ----------
s = p.addSlide(); s.background = { color: WHITE };
kicker(s, "Beyond labour savings", M, 0.55);
title(s, "The real upside goes beyond hours", M, 0.9);
const val = [
  ["Faster time-to-fill", "Vacancy live same day -> placement sooner -> margin sooner."],
  ["Better findability", "Consistent SEO/GEO -> more organic traffic, less budget-dependent."],
  ["Lead tracking", "Every Meta lead traceable to the vacancy via App Id - steer better."],
  ["Scalable without headcount", "Absorb volume peaks; recruiters focus on candidates."],
];
val.forEach(function (it, i) {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.2, y = 2.15 + row * 1.85, w = 5.9, h = 1.6;
  card(s, x, y, w, h, WHITE);
  s.addShape(p.shapes.RECTANGLE, { x: x, y: y, w: 0.09, h: h, fill: { color: ORANGE } });
  s.addText(it[0], { x: x + 0.32, y: y + 0.25, w: w - 0.6, h: 0.45, fontFace: HEAD, bold: true, fontSize: 17, color: INK, margin: 0 });
  s.addText(it[1], { x: x + 0.32, y: y + 0.72, w: w - 0.6, h: 0.75, fontFace: BODY, fontSize: 13, color: MUTED, lineSpacing: 18, margin: 0 });
});
s.addShape(p.shapes.RECTANGLE, { x: M, y: 5.95, w: W - 2 * M, h: 0.85, fill: { color: ORANGE } });
s.addText("One extra placement per month from faster turnaround already outweighs the entire labour saving.", { x: M + 0.3, y: 5.95, w: W - 2 * M - 0.6, h: 0.85, valign: "middle", fontFace: HEAD, bold: true, fontSize: 16, color: WHITE, margin: 0 });

// ---------- Slide 10 — RECOMMENDATION ----------
s = p.addSlide(); s.background = { color: DARK };
bracketPair(s, 10.0, 1.4, 2.7, 2.3, ORANGE, 0.05, 0.5);
s.addText("TECQ", { x: 10.0, y: 2.25, w: 2.7, h: 0.6, align: "center", fontFace: DISP, fontSize: 30, color: WHITE, margin: 0 });
kicker(s, "Recommendation", M, 1.3);
s.addText("Push on - and scale up", { x: M, y: 1.75, w: 9, h: 1.0, fontFace: DISP, fontSize: 38, color: WHITE, margin: 0 });
[
  ["Ongoing costs negligible", "~ € 2-3 per vacancy in AI + ~ € 25/month hosting."],
  ["The saving is already structural", "≈ € 71k/year and ~0.8 FTE, from day one."],
  ["Next steps", "Add recruiter sourcing · own photo library · direct website publishing · roll out across Maintec and Tecforce."],
].forEach(function (it, i) {
  const y = 3.05 + i * 1.05;
  s.addShape(p.shapes.RECTANGLE, { x: M, y: y, w: 0.09, h: 0.85, fill: { color: ORANGE } });
  s.addText(it[0], { x: M + 0.3, y: y, w: 8.6, h: 0.4, fontFace: HEAD, bold: true, fontSize: 16.5, color: WHITE, margin: 0 });
  s.addText(it[1], { x: M + 0.3, y: y + 0.4, w: 8.6, h: 0.5, fontFace: BODY, fontSize: 13, color: "B9B8B6", margin: 0 });
});
s.addText("Join the Future Techforce.", { x: M, y: 6.65, w: 9, h: 0.45, fontFace: HEAD, bold: true, italic: true, fontSize: 16, color: ORANGE, margin: 0 });

p.writeFile({ fileName: "VIF-automation-business-case.pptx" }).then(function (fn) {
  console.log("OK written: " + fn);
});
