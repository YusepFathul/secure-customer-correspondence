// Builds presentation/Secure_Customer_Correspondence.pptx from reports produced by scripts/run_all.py
// (numbers come from presentation/deck_data.json). Run: node presentation/build_deck.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("/mnt/skills/public/pptx/scripts/apply_theme.js");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "deck_data.json"), "utf8"));
const OUT = path.join(__dirname, "Secure_Customer_Correspondence.pptx");

const THEME = {
  name: "Secure Correspondence",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2433", lt1: "FFFFFF", dk2: "14324F", lt2: "F1F4F8",
    accent1: "14324F", // navy - process
    accent2: "1F8A5B", // green - outcomes
    accent3: "C97B06", // amber - problems
    accent4: "17808F", // teal - data protection
    accent5: "5B7088", // slate - governance
    accent6: "B03A2E", // red - critical
    hlink: "1F6FB2", folHlink: "5B7088",
  },
};
const HEX = THEME.colors;

const SHORT = {
  "DP-01": "Letter missing", "DP-02": "Duplicate letter", "DP-03": "Ambiguous file name",
  "DP-04": "Content not recipient's", "DP-05": "Orphan letter", "DP-06": "Email differs / typo",
  "DP-07": "Wrong or manual CC", "DP-08": "Multiple recipients", "DP-10": "NIK in file name",
};

async function icon(Comp, hex, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.author = "Yusep Fathul Anwar";
  pres.title = "Secure Customer Correspondence";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "TITLE_DARK",
    background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.5, fontSize: 40,
        bold: true, color: C.background1, fontFace: THEME.headFontFace, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.95, w: 11.0, h: 1.6, fontSize: 18,
        color: "CADCFC", valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    margin: [0.5, 0.6, 0.6, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 1.0, fontSize: 24,
        bold: true, color: C.text2, fontFace: THEME.headFontFace, valign: "top", align: "left", margin: 0 }, text: "" } },
      { text: { text: "Secure Customer Correspondence  |  synthetic data", options: { x: 0.6, y: 7.0, w: 8, h: 0.3,
        fontSize: 9, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 12.3, y: 7.0, w: 0.4, h: 0.3, fontSize: 9, color: HEX.accent5, align: "right" },
  });

  const foot = (s, text) => s.addText(text, { x: 0.6, y: 6.55, w: 12.1, h: 0.35, fontSize: 10, color: C.accent5,
    italic: true, margin: 0, isTextBox: true, objectName: "footnote" });
  const card = (s, x, y, w, h, name, fill = C.background2) => s.addShape(pres.shapes.ROUNDED_RECTANGLE,
    { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: name });
  const circleIcon = async (s, Comp, x, y, d, fillKey, name) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C[fillKey] }, line: { color: C[fillKey] },
      objectName: name + " circle" });
    const pad = d * 0.24;
    s.addImage({ data: await icon(Comp, "FFFFFF"), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad,
      objectName: name + " icon" });
  };

  // ---------------------------------------------------------------- 1. Title
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  s.addText("Secure Customer Correspondence", { placeholder: "title" });
  s.addText([
    { text: "Redesigning customer letter delivery with built-in data protection and governance", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 10 } },
    { text: "Yusep Fathul Anwar  |  Portfolio case study  |  Synthetic data", options: { fontSize: 14, color: "9DB4CC" } },
  ], { placeholder: "body" });
  s.addNotes("This is a public, synthetic rebuild of the kind of process I improve at work: sending letters that contain personal data to customers by email, with the branch in CC. The goal was to make it faster, impossible to misdirect, and auditable.");

  // ---------------------------------------------------------------- 2. Executive summary
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("Automating letter delivery cut effort ~30x and sent zero letters to the wrong person", { placeholder: "title" });
  const ratio = Math.round(D.as_is_min / D.to_be_min);
  const pillars = [
    { name: "Process improvement", icon: fa.FaBolt, color: "accent1", stat: `~${ratio}x`,
      label: "less effort per 150-letter batch (10 h to 20 min)",
      pts: ["Matching, addressing, locking and sending automated", `~${Math.round(D.machine_seconds_avg)} s processing per batch`] },
    { name: "Data protection", icon: fa.FaShieldAlt, color: "accent4", stat: String(D.kpi.defects_leaked),
      label: "letters reached the wrong person",
      pts: ["13 controls before any email leaves", `${D.kpi.defects_caught} of ${D.kpi.injected_defects} injected defects caught`] },
    { name: "Governance", icon: fa.FaBalanceScale, color: "accent5", stat: "3 / 3",
      label: "batches approved by a second person",
      pts: ["Maker-checker enforced by the system", "Audit trail, monthly report, incident playbook"] },
  ];
  for (let i = 0; i < 3; i++) {
    const p = pillars[i], x = 0.6 + i * 4.15, y = 1.55, w = 3.85;
    card(s, x, y, w, 4.35, p.name + " card");
    await circleIcon(s, p.icon, x + 0.3, y + 0.3, 0.7, p.color, p.name);
    s.addText(p.name, { x: x + 1.15, y: y + 0.38, w: w - 1.3, h: 0.55, fontSize: 17, bold: true, color: C.text2,
      margin: 0, valign: "middle", isTextBox: true, objectName: p.name + " heading" });
    s.addText(p.stat, { x: x + 0.3, y: y + 1.25, w: w - 0.6, h: 1.0, fontSize: 48, bold: true, color: C.accent2,
      fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: p.name + " stat" });
    s.addText(p.label, { x: x + 0.3, y: y + 2.25, w: w - 0.6, h: 0.65, fontSize: 14, color: C.text1, margin: 0,
      valign: "top", isTextBox: true, objectName: p.name + " stat label" });
    s.addText(p.pts.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < p.pts.length - 1 } })),
      { x: x + 0.3, y: y + 3.05, w: w - 0.6, h: 1.5, fontSize: 14, color: C.accent5, margin: 0, valign: "top",
        paraSpaceAfter: 6, isTextBox: true, objectName: p.name + " points" });
  }
  foot(s, "Simulation on synthetic data, Aug-Oct 2026, 450 customers. As-Is effort assumed at 4 minutes per letter.");
  s.addNotes("Three pillars, one process. The headline: a batch that took a working day by hand takes about twenty minutes, and across three months not a single letter went to the wrong person, even though I deliberately injected 42 realistic mistakes.");

  // ---------------------------------------------------------------- 3. Context
  pres.addSection({ title: "Problem" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
  s.addText("Every month, letters carrying the customer's NIK are emailed to the customer with the branch in CC", { placeholder: "title" });
  const nodes = [
    { t: "Send list", d: "Customers due a letter this month", ic: fa.FaListAlt },
    { t: "Letter PDF", d: "Name, policy number and NIK", ic: fa.FaFilePdf },
    { t: "Email", d: "To: the customer\nCC: their servicing branch", ic: fa.FaEnvelope },
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 2.75, y = 1.9;
    card(s, x, y, 2.3, 3.0, nodes[i].t + " card");
    await circleIcon(s, nodes[i].ic, x + 0.75, y + 0.3, 0.8, "accent1", nodes[i].t);
    s.addText(nodes[i].t, { x: x + 0.15, y: y + 1.25, w: 2.0, h: 0.45, fontSize: 17, bold: true, color: C.text2,
      align: "center", margin: 0, isTextBox: true, objectName: nodes[i].t + " label" });
    s.addText(nodes[i].d, { x: x + 0.15, y: y + 1.75, w: 2.0, h: 1.0, fontSize: 14, color: C.text1,
      align: "center", valign: "top", margin: 0, isTextBox: true, objectName: nodes[i].t + " desc" });
    if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.37, y: y + 1.3, w: 0.33, h: 0.4,
      fill: { color: C.accent5 }, line: { color: C.accent5 }, objectName: "arrow " + i });
  }
  const facts = [
    [String(D.kpi.customers), "customers across 3 monthly batches"],
    ["3", "letter types: maturity, benefit payment, reinstatement"],
    ["6", "branches, each allowed to see only its own customers"],
    ["1", "NIK in every single letter"],
  ];
  facts.forEach(([n, t], i) => {
    const y = 1.75 + i * 1.12;
    s.addText(n, { x: 9.15, y, w: 1.2, h: 0.85, fontSize: 36, bold: true, color: C.text2, fontFace: THEME.headFontFace,
      margin: 0, valign: "middle", isTextBox: true, objectName: "fact number " + i });
    s.addText(t, { x: 10.4, y, w: 2.3, h: 0.85, fontSize: 14, color: C.text1, margin: 0, valign: "middle",
      isTextBox: true, objectName: "fact text " + i });
  });
  s.addText("Under UU PDP (Law No. 27/2022), a letter that reaches the wrong person is a personal data protection failure that must be reported within 3 x 24 hours.",
    { x: 0.6, y: 5.3, w: 8.0, h: 0.8, fontSize: 14, color: C.accent3, bold: true, margin: 0, valign: "top",
      isTextBox: true, objectName: "regulatory note" });
  s.addNotes("The data is sensitive by design: every letter carries the NIK, and every email copies a branch. So two things can go wrong: the wrong customer, or the wrong branch.");

  // ---------------------------------------------------------------- 4. Problem (As-Is)
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
  s.addText("Done by hand, the process is slow and every manual step is a chance for personal data to leak", { placeholder: "title" });
  const steps = [
    ["Match PDF to the list by eye", "Wrong customer's letter attached"],
    ["Copy the customer email", "Old or mistyped address"],
    ["Type the branch email in CC", "Another branch sees the data"],
    ["Attach the PDF", "NIK travels unprotected"],
    ["Send one by one", "No record of who sent what"],
  ];
  steps.forEach(([st, risk], i) => {
    const x = 0.6 + i * 2.45, w = 2.15;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w, h: 1.25, fill: { color: C.background1 },
      line: { color: C.text2, width: 1.25 }, rectRadius: 0.08, objectName: "as-is step " + (i + 1) });
    s.addText([{ text: `${i + 1}`, options: { bold: true, color: C.accent5, breakLine: true } }, { text: st }],
      { x: x + 0.15, y: 1.8, w: w - 0.3, h: 1.15, fontSize: 14, color: C.text2, margin: 0, valign: "middle",
        align: "center", isTextBox: true, objectName: "as-is step text " + (i + 1) });
    if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + 0.05, y: 2.22, w: 0.2, h: 0.3,
      fill: { color: C.accent5 }, line: { color: C.accent5 }, objectName: "as-is arrow " + i });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.25, w, h: 1.15, fill: { color: "FBF1E0" },
      line: { color: "FBF1E0" }, rectRadius: 0.08, objectName: "risk " + (i + 1) });
    s.addText([{ text: "Risk", options: { bold: true, breakLine: true, fontSize: 11 } }, { text: risk }],
      { x: x + 0.15, y: 3.3, w: w - 0.3, h: 1.05, fontSize: 14, color: "8A5404", margin: 0, valign: "middle",
        align: "center", isTextBox: true, objectName: "risk text " + (i + 1) });
  });
  card(s, 0.6, 4.75, 12.1, 1.45, "effort callout");
  s.addText(String(Math.round(D.as_is_min / 60)) + " hours", { x: 0.9, y: 4.85, w: 2.6, h: 1.25, fontSize: 40, bold: true,
    color: C.accent3, fontFace: THEME.headFontFace, margin: 0, valign: "middle", isTextBox: true, objectName: "effort number" });
  s.addText("of manual work for one 150-letter batch, with no second pair of eyes before sending and no evidence afterwards.",
    { x: 3.6, y: 4.85, w: 8.8, h: 1.25, fontSize: 16, color: C.text1, margin: 0, valign: "middle", isTextBox: true,
      objectName: "effort text" });
  foot(s, "Effort assumes 4 minutes per letter for matching, addressing, attaching and sending.");
  s.addNotes("Each manual step maps to a specific way data can leak. That observation drives the whole design: if the failure modes are predictable, each one can get a control.");

  // ---------------------------------------------------------------- 5. Insight
  pres.addSection({ title: "Solution" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
  s.addText("Leaks come from a few predictable failure modes, so each one can be blocked by a specific control", { placeholder: "title" });
  const groups = [
    { h: "Right document", ic: fa.FaFileAlt, items: ["DP-01  Every customer has a letter", "DP-02  No duplicate letters",
      "DP-03  File name points to one policy", "DP-04  Policy, name and NIK match recipient", "DP-05  No orphan letters"] },
    { h: "Right recipient", ic: fa.FaUserCheck, items: ["DP-06  Email equals master data, no typo",
      "DP-07  Branch CC taken from branch master", "DP-08  One customer per email, no BCC"] },
    { h: "Data protected", ic: fa.FaLock, items: ["DP-09  Letter locked with the customer's password",
      "DP-10  No NIK in file name, subject or body", "DP-11  Logs and reports hold masked data only"] },
    { h: "Safe delivery", ic: fa.FaPaperPlane, items: ["DP-12  Official mailbox only, no credentials in code",
      "DP-13  File identical to the approved version", "Kill switch halts the batch on anomalies"] },
  ];
  for (let i = 0; i < 4; i++) {
    const g = groups[i], x = 0.6 + (i % 2) * 6.15, y = 1.55 + Math.floor(i / 2) * 2.55, w = 5.95, h = 2.35;
    card(s, x, y, w, h, g.h + " card");
    await circleIcon(s, g.ic, x + 0.25, y + 0.22, 0.55, "accent4", g.h);
    s.addText(g.h, { x: x + 0.95, y: y + 0.22, w: w - 1.2, h: 0.55, fontSize: 17, bold: true, color: C.text2, margin: 0,
      valign: "middle", isTextBox: true, objectName: g.h + " heading" });
    s.addText(g.items.map((t, j) => ({ text: t, options: { breakLine: j < g.items.length - 1 } })),
      { x: x + 0.3, y: y + 0.9, w: w - 0.5, h: h - 1.0, fontSize: 14, color: C.text1, margin: 0, valign: "top",
        paraSpaceAfter: 2, isTextBox: true, objectName: g.h + " controls" });
  }
  s.addNotes("I grouped thirteen controls by the question they answer: is it the right document, the right recipient, is the data protected, and is delivery safe. DP-04 and DP-07 are the critical ones for this role: wrong customer and wrong branch.");

  // ---------------------------------------------------------------- 6. To-Be process
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
  s.addText("The redesigned process validates, locks and requires two people before any email leaves", { placeholder: "title" });
  const flow = [
    ["Validate", "13 controls on every letter and recipient", "accent4"],
    ["Quarantine", "Failures copied aside, never sent", "accent4"],
    ["Lock", "PDF password = customer's date of birth", "accent4"],
    ["Maker submits", "Reviews held items; batch fingerprinted", "accent5"],
    ["Checker approves", "A different person; cannot be the maker", "accent5"],
    ["Send", "Dry run first; 1 email per customer", "accent1"],
    ["Verify & report", "Outbox re-checked; audit trail; report", "accent5"],
  ];
  flow.forEach(([t, d, col], i) => {
    const x = 0.6 + i * 1.75, cx = x + 0.75;
    s.addShape(pres.shapes.OVAL, { x: cx - 0.35, y: 1.65, w: 0.7, h: 0.7, fill: { color: C[col] }, line: { color: C[col] },
      objectName: "flow circle " + (i + 1) });
    s.addText(String(i + 1), { x: cx - 0.35, y: 1.65, w: 0.7, h: 0.7, fontSize: 18, bold: true, color: C.background1,
      align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "flow number " + (i + 1) });
    if (i < 6) s.addShape(pres.shapes.LINE, { x: cx + 0.42, y: 2.0, w: 0.91, h: 0, line: { color: C.accent5, width: 1.25,
      endArrowType: "triangle" }, objectName: "flow connector " + i });
    s.addText(t, { x, y: 2.5, w: 1.55, h: 0.6, fontSize: 14, bold: true, color: C.text2, align: "center", margin: 0,
      valign: "top", isTextBox: true, objectName: "flow title " + (i + 1) });
    s.addText(d, { x, y: 3.1, w: 1.55, h: 1.1, fontSize: 12, color: C.text1, align: "center", margin: 0, valign: "top",
      isTextBox: true, objectName: "flow desc " + (i + 1) });
  });
  [["Data protection", "accent4"], ["Governance", "accent5"], ["Process improvement", "accent1"]].forEach(([l, col], i) => {
    const x = 0.6 + i * 2.6;
    s.addShape(pres.shapes.OVAL, { x, y: 4.45, w: 0.2, h: 0.2, fill: { color: C[col] }, line: { color: C[col] },
      objectName: "legend dot " + l });
    s.addText(l, { x: x + 0.3, y: 4.38, w: 2.2, h: 0.35, fontSize: 12, color: C.accent5, margin: 0, valign: "middle",
      isTextBox: true, objectName: "legend " + l });
  });
  card(s, 0.6, 4.95, 12.1, 1.45, "example card");
  s.addText([
    { text: "Example  ", options: { bold: true, color: C.accent4 } },
    { text: "Budi W*****, Bandung branch: To customer.0002@gmail.example, CC branch.bdg@nusantaralife.example only. The attachment holds Budi's own policy and masked NIK and opens only with his date of birth. Surabaya never receives anything about Budi.", options: { color: C.text1 } },
  ], { x: 0.9, y: 5.05, w: 11.5, h: 1.25, fontSize: 15, margin: 0, valign: "middle", isTextBox: true, objectName: "example text" });
  s.addNotes("Steps one to three protect the data, four and five are the governance gate, six is the efficiency gain, seven produces the evidence. The branch CC is never typed by a person: it is looked up from branch master data using the customer's own branch.");

  // ---------------------------------------------------------------- 7. Governance
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
  s.addText("Governance is enforced by the system, not left to good intentions", { placeholder: "title" });
  const gov = [
    { h: "Maker-checker", ic: fa.FaUserFriends, t: "The maker submits, a different checker approves. The batch is fingerprinted at submission; any later change forces a resubmission." },
    { h: "Kill switch", ic: fa.FaPowerOff, t: "The batch halts automatically if more than 20% is quarantined, any file changes after approval, or sending fails repeatedly." },
    { h: "Audit trail", ic: fa.FaClipboardList, t: "Every validation, approval and email is logged with personal data masked; every run scans logs and reports for raw NIK." },
    { h: "Governance documents", ic: fa.FaBook, t: "Risk & control matrix (16 risks), RACI and SOP, and an incident playbook with the UU PDP 3 x 24 hour notification." },
  ];
  for (let i = 0; i < 4; i++) {
    const g = gov[i], x = 0.6 + (i % 2) * 6.15, y = 1.55 + Math.floor(i / 2) * 2.5, w = 5.95, h = 2.3;
    card(s, x, y, w, h, g.h + " card");
    await circleIcon(s, g.ic, x + 0.3, y + 0.3, 0.75, "accent5", g.h);
    s.addText(g.h, { x: x + 1.3, y: y + 0.3, w: w - 1.5, h: 0.5, fontSize: 18, bold: true, color: C.text2, margin: 0,
      valign: "middle", isTextBox: true, objectName: g.h + " heading" });
    s.addText(g.t, { x: x + 1.3, y: y + 0.85, w: w - 1.55, h: h - 1.05, fontSize: 14, color: C.text1, margin: 0,
      valign: "top", isTextBox: true, objectName: g.h + " text" });
  }
  s.addNotes("This is the governance part of the role: segregation of duties, a hard stop, evidence, and a written procedure for when something still goes wrong.");

  // ---------------------------------------------------------------- 8. Evidence 1
  pres.addSection({ title: "Evidence" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
  s.addText(`All ${D.kpi.injected_defects} deliberately injected defects were caught and none reached a customer`, { placeholder: "title" });
  const bc = D.by_control.slice().reverse();
  s.addChart(pres.charts.BAR, [{ name: "Documents held", labels: bc.map(r => `${r.id}  ${SHORT[r.id]}`), values: bc.map(r => r.n) }], {
    x: 0.6, y: 1.5, w: 7.4, h: 4.9, barDir: "bar", chartColors: [HEX.accent4], barGapWidthPct: 70,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.dk1, dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisLineShow: false,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "Documents held by control, Aug-Oct 2026", titleFontSize: 14, titleColor: HEX.dk2,
    titleFontFace: "+mn-lt", objectName: "held by control chart",
  });
  const stats = [
    [`${D.kpi.defects_caught} / ${D.kpi.injected_defects}`, "injected defects caught by the intended control"],
    [String(D.kpi.defects_leaked), "defects that reached a customer"],
    [String(D.kpi.false_positives), "clean letters held by mistake"],
  ];
  stats.forEach(([n, t], i) => {
    const y = 1.6 + i * 1.6;
    card(s, 8.4, y, 4.3, 1.4, "stat card " + i);
    s.addText(n, { x: 8.65, y: y + 0.1, w: 1.9, h: 1.2, fontSize: 36, bold: true, color: C.accent2,
      fontFace: THEME.headFontFace, margin: 0, valign: "middle", isTextBox: true, objectName: "stat " + i });
    s.addText(t, { x: 10.55, y: y + 0.1, w: 2.0, h: 1.2, fontSize: 14, color: C.text1, margin: 0, valign: "middle",
      isTextBox: true, objectName: "stat label " + i });
  });
  foot(s, "Injected per batch: swapped letters, foreign NIK, stale and mistyped emails, wrong branch, manual external CC, two recipients, NIK in file name, missing, duplicate, ambiguous and orphan files.");
  s.addNotes("To prove the controls rather than claim them, I injected realistic mistakes into every batch and kept a ground-truth list. Every one was caught by the control designed for it, and no clean letter was held.");

  // ---------------------------------------------------------------- 9. Evidence 2
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
  s.addText(`An independent re-check of all ${D.kpi.emails_sent} sent emails shows each branch received only its own customers`, { placeholder: "title" });
  const M = D.matrix;
  const hdr = [{ text: "CC to \\ data of", options: { bold: true, color: C.accent5, fontSize: 11 } },
    ...M.cols.map(c => ({ text: c, options: { bold: true, color: C.text2, align: "center" } }))];
  const rows = [hdr, ...M.rows.map((r, i) => [
    { text: r, options: { bold: true, color: C.text2 } },
    ...M.values[i].map((v, j) => ({ text: String(v), options: { align: "center", color: i === j ? HEX.dk2 : "9AA5B1",
      bold: i === j, fill: { color: i === j ? "D8EFE3" : "F7F8FA" } } })),
  ])];
  s.addTable(rows, { x: 0.6, y: 1.65, w: 6.3, colW: [1.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8], rowH: 0.52, fontSize: 14,
    fontFace: "Calibri", color: C.text1, border: { type: "solid", pt: 1, color: "FFFFFF" }, valign: "middle",
    objectName: "leakage matrix table" });
  s.addText("Rows: branch mailbox that received the CC. Columns: branch that owns the customer's data. Anything off the diagonal would be a leak.",
    { x: 0.6, y: 5.45, w: 6.3, h: 0.8, fontSize: 12, color: C.accent5, margin: 0, valign: "top", isTextBox: true,
      objectName: "matrix caption" });
  const checks = [
    "Attachment opens only with the recipient's own password",
    "Attachment holds only the recipient's policy and NIK",
    "CC goes only to the customer's own branch",
    "No NIK in subject or body; one customer per email",
  ];
  const ok = await icon(fa.FaCheckCircle, HEX.accent2);
  checks.forEach((t, i) => {
    const y = 1.7 + i * 0.95;
    s.addImage({ data: ok, x: 7.4, y: y + 0.08, w: 0.4, h: 0.4, objectName: "check icon " + i });
    s.addText([{ text: `${D.kpi.emails_sent} / ${D.kpi.emails_sent}  `, options: { bold: true, color: C.accent2 } },
      { text: t, options: { color: C.text1 } }], { x: 7.95, y, w: 4.75, h: 0.8, fontSize: 14, margin: 0,
      valign: "top", isTextBox: true, objectName: "check text " + i });
  });
  card(s, 7.4, 5.55, 5.3, 0.85, "pii scan card");
  s.addText("0 raw NIK, email addresses or birth dates found in logs and reports (DP-11 scan)", { x: 7.6, y: 5.6,
    w: 5.0, h: 0.75, fontSize: 14, bold: true, color: C.text2, margin: 0, valign: "middle", isTextBox: true,
    objectName: "pii scan text" });
  s.addNotes("This check does not trust the pipeline. It opens every email in the outbox, tries the attachment with the To recipient's own password and reads what is inside. The matrix shows only the diagonal is filled.");

  // ---------------------------------------------------------------- 10. Impact
  pres.addSection({ title: "Impact and next steps" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact and next steps" });
  s.addText("Effort per batch falls from about 10 hours to 20 minutes while control coverage rises from none to 13 checks", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Minutes per batch", labels: ["As-Is (manual, assumed)", "To-Be"],
    values: [Math.round(D.as_is_min), Math.round(D.to_be_min)] }], {
    x: 0.6, y: 1.6, w: 5.4, h: 4.6, barDir: "col", chartColors: ["9DB4CC", HEX.accent2], barGapWidthPct: 60,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.dk1, dataLabelFontSize: 14, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "Minutes per 150-letter batch", titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt",
    varyColors: true, objectName: "effort chart",
  });
  const cmp = [
    ["", "As-Is", "To-Be"],
    ["Effort per batch", "~10 hours", "~20 minutes"],
    ["Processing", "Manual", `~${Math.round(D.machine_seconds_avg)} seconds`],
    ["Wrong-recipient protection", "Staff attention", "13 automated controls"],
    ["NIK protection", "None", "Password-locked letter"],
    ["Review before sending", "Ad hoc", "Maker-checker"],
    ["Evidence", "None", "Audit trail and report"],
  ];
  s.addTable(cmp.map((r, i) => r.map((v, j) => ({ text: v, options: {
    bold: i === 0 || j === 0, color: i === 0 ? C.background1 : (j === 2 ? HEX.accent2 : (j === 1 ? "8A5404" : C.text2)),
    fill: { color: i === 0 ? HEX.dk2 : (i % 2 ? "FFFFFF" : "F1F4F8") } } }))),
    { x: 6.5, y: 1.65, w: 6.2, colW: [2.3, 1.75, 2.15], rowH: 0.62, fontSize: 14, fontFace: "Calibri", valign: "middle",
      border: { type: "solid", pt: 1, color: "FFFFFF" }, objectName: "before after table" });
  foot(s, "As-Is assumes 4 minutes per letter; To-Be assumes 20 minutes of maker review and checker approval plus measured processing time.");
  s.addNotes("The time saving is large, but the bigger change is qualitative: the process now has controls, a second pair of eyes and evidence, none of which existed before. The time assumptions are explicit and should be replaced with a real time study.");

  // ---------------------------------------------------------------- 11. Next steps
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact and next steps" });
  s.addText("Three changes remove the most frequent exceptions at their source; then the design is ready to pilot", { placeholder: "title" });
  const held = Object.fromEntries(D.by_control.map(r => [r.id, r.n]));
  const recs = [
    ["Build the send list directly from master data", `Stale and mistyped emails were the top exception (DP-06, ${held["DP-06"]} held)`],
    ["Remove the manual CC column from the template", `Branch mailboxes come from branch master only (DP-07, ${held["DP-07"]} held)`],
    ["Enforce file naming at letter generation", `Letter type + policy + period, never the NIK (DP-03 and DP-10, ${held["DP-03"] + held["DP-10"]} held)`],
  ];
  s.addText("Fix at source", { x: 0.6, y: 1.5, w: 6.6, h: 0.45, fontSize: 18, bold: true, color: C.text2, margin: 0,
    isTextBox: true, objectName: "fix heading" });
  recs.forEach(([h, d], i) => {
    const y = 2.1 + i * 1.45;
    s.addShape(pres.shapes.OVAL, { x: 0.6, y, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1 },
      objectName: "rec circle " + i });
    s.addText(String(i + 1), { x: 0.6, y, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: "rec number " + i });
    s.addText([{ text: h, options: { bold: true, color: C.text2, breakLine: true } }, { text: d, options: { color: C.text1 } }],
      { x: 1.4, y: y - 0.05, w: 5.8, h: 1.2, fontSize: 14, margin: 0, valign: "top", isTextBox: true, objectName: "rec text " + i });
  });
  card(s, 7.6, 1.5, 5.1, 4.2, "pilot card");
  s.addText("Path to production", { x: 7.9, y: 1.7, w: 4.6, h: 0.45, fontSize: 18, bold: true, color: C.text2, margin: 0,
    isTextBox: true, objectName: "pilot heading" });
  const pilot = ["Pilot one letter type in one branch for one month", "Run a time study to replace the assumed As-Is effort",
    "Switch the transport to SMTP with credentials from a secrets vault", "Consider an SMS one-time password instead of date of birth",
    "Review the monthly control report with the DPO"];
  s.addText(pilot.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < pilot.length - 1 } })),
    { x: 7.9, y: 2.3, w: 4.6, h: 3.2, fontSize: 14, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 10,
      isTextBox: true, objectName: "pilot steps" });
  s.addNotes("The monthly report does not only count exceptions; it says where to fix them. Most exceptions come from manual edits upstream, so the cheapest control is removing the manual step.");

  // ---------------------------------------------------------------- 12. Closing
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Impact and next steps" });
  s.addText("Faster. Leak-proof. Auditable.", { placeholder: "title" });
  s.addText([
    { text: "Code, synthetic data, governance documents and 22 tests:", options: { breakLine: true } },
    { text: "github.com/YusepFathul/secure-customer-correspondence", options: { bold: true, color: "FFFFFF", breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 10 } },
    { text: "Yusep Fathul Anwar  |  linkedin.com/in/yusepfathulanwar", options: { fontSize: 14, color: "9DB4CC" } },
  ], { placeholder: "body" });
  s.addNotes("Happy to walk through the code or the control room live.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
