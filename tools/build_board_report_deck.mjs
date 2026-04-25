import fs from "node:fs/promises";
import path from "node:path";

import { Presentation, PresentationFile } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_board_report_deck.mjs <input.json> <output.pptx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { report, session_summary: sessionSummary } = payload;
const presentation = Presentation.create({
  slideSize: { width: 1280, height: 720 },
});

const COLORS = {
  bg: "#F6F1E8",
  ink: "#132238",
  deep: "#153B5C",
  accent: "#C86A3B",
  soft: "#E6D6C4",
  risk: "#A6403B",
  action: "#2D6A4F",
};

function titleBlock(slide, title, subtitle) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: 0, top: 0, width: 1280, height: 720 },
    fill: COLORS.bg,
    line: { width: 0, fill: COLORS.bg },
  });
  const titleShape = slide.shapes.add({
    geometry: "rect",
    position: { left: 72, top: 54, width: 1130, height: 90 },
    fill: COLORS.bg,
    line: { width: 0, fill: COLORS.bg },
  });
  titleShape.text = title;
  titleShape.text.fontSize = 34;
  titleShape.text.bold = true;
  titleShape.text.color = COLORS.deep;
  titleShape.text.typeface = "Poppins";

  const subtitleShape = slide.shapes.add({
    geometry: "rect",
    position: { left: 72, top: 122, width: 900, height: 54 },
    fill: COLORS.bg,
    line: { width: 0, fill: COLORS.bg },
  });
  subtitleShape.text = subtitle;
  subtitleShape.text.fontSize = 18;
  subtitleShape.text.color = COLORS.ink;
  subtitleShape.text.typeface = "Lato";
}

function addBulletBox(slide, left, top, width, height, header, bullets, fill) {
  slide.shapes.add({
    geometry: "roundRect",
    position: { left, top, width, height },
    fill,
    line: { width: 0, fill },
    adjustmentList: [{ name: "adj", formula: "val 18000" }],
  });
  const headerShape = slide.shapes.add({
    geometry: "rect",
    position: { left: left + 18, top: top + 16, width: width - 36, height: 30 },
    fill,
    line: { width: 0, fill },
  });
  headerShape.text = header;
  headerShape.text.fontSize = 20;
  headerShape.text.bold = true;
  headerShape.text.color = COLORS.deep;
  headerShape.text.typeface = "Poppins";

  const body = slide.shapes.add({
    geometry: "rect",
    position: { left: left + 18, top: top + 56, width: width - 36, height: height - 70 },
    fill,
    line: { width: 0, fill },
  });
  body.text = bullets.map((item) => `- ${item}`);
  body.text.fontSize = 16;
  body.text.color = COLORS.ink;
  body.text.typeface = "Lato";
  body.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };
}

const title = presentation.slides.add();
titleBlock(
  title,
  `${report.source.company_name} Board Update`,
  `${report.source.quarter_label} | Meeting ${report.source.board_meeting_date}`,
);
const takeShape = title.shapes.add({
  geometry: "roundRect",
  position: { left: 72, top: 205, width: 1136, height: 130 },
  fill: COLORS.soft,
  line: { width: 0, fill: COLORS.soft },
  adjustmentList: [{ name: "adj", formula: "val 17000" }],
});
takeShape.text = report.executive_takeaway;
takeShape.text.fontSize = 24;
takeShape.text.bold = true;
takeShape.text.color = COLORS.deep;
takeShape.text.typeface = "Poppins";
takeShape.text.insets = { left: 22, right: 22, top: 18, bottom: 18 };

addBulletBox(title, 72, 370, 350, 250, "Top Drivers", report.source.top_drivers.slice(0, 3), "#EFE4D7");
addBulletBox(title, 465, 370, 350, 250, "Top Risks", report.source.top_risks.slice(0, 3), "#F4DEDA");
addBulletBox(title, 858, 370, 350, 250, "Top Actions", report.source.top_actions.slice(0, 3), "#E3EFE7");

const metrics = presentation.slides.add();
titleBlock(metrics, "Financial Highlights", "Bold takeaway first, then plan and prior-period evidence");
metrics.charts.add("bar", {
  title: "Quarter KPI Snapshot",
  categories: report.source.financial_highlights.map((item) => item.name),
  series: [
    { name: "Actual", values: report.source.financial_highlights.map((item) => item.actual), fill: COLORS.deep },
    { name: "Plan", values: report.source.financial_highlights.map((item) => item.plan), fill: COLORS.accent },
  ],
  hasLegend: true,
  legend: { position: "top" },
  barOptions: { direction: "column", grouping: "clustered", gapWidth: 80 },
  dataLabels: { showValue: false },
  from: { row: 3, col: 7 },
  extent: { widthPx: 570, heightPx: 290 },
});
addBulletBox(metrics, 72, 210, 480, 390, "Highlights", report.financial_highlights.slice(0, 5), "#EFE4D7");

const strategy = presentation.slides.add();
titleBlock(strategy, "Strategy, Risks, and Management Response", report.source.business_model);
addBulletBox(strategy, 72, 198, 360, 420, "Strategic Updates", report.strategic_narrative.slice(0, 4), "#EFE4D7");
addBulletBox(strategy, 460, 198, 360, 420, "Risks", report.risk_narrative.slice(0, 3), "#F4DEDA");
addBulletBox(strategy, 848, 198, 360, 420, "Actions", report.action_narrative.slice(0, 3), "#E3EFE7");

const outlook = presentation.slides.add();
titleBlock(outlook, "Outlook and Board Discussion", "Forward view, management posture, and CHP hardening summary");
if (report.source.trend_series.length > 0) {
  const trend = report.source.trend_series[0];
  outlook.charts.add("line", {
    title: trend.name,
    categories: trend.labels,
    series: [
      { name: "Actual", values: trend.actual, stroke: { width: 3, style: "solid", fill: COLORS.deep }, fill: COLORS.deep },
      { name: "Plan", values: trend.plan, stroke: { width: 3, style: "solid", fill: COLORS.accent }, fill: COLORS.accent },
    ],
    hasLegend: true,
    legend: { position: "top" },
    dataLabels: { showValue: false },
    lineOptions: { grouping: "standard", smooth: false },
    from: { row: 3, col: 7 },
    extent: { widthPx: 560, heightPx: 270 },
  });
}
addBulletBox(outlook, 72, 220, 480, 230, "Outlook", report.source.outlook.slice(0, 4), "#EFE4D7");
addBulletBox(outlook, 72, 470, 1136, 150, "CHP Session Summary", [sessionSummary], "#EAE7F2");

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPath);
