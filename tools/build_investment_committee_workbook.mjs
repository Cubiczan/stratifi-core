import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_investment_committee_workbook.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { committee, session_summary: sessionSummary } = payload;
const workbook = Workbook.create();

const summarySheet = workbook.worksheets.add("Summary");
const scorecardSheet = workbook.worksheets.add("Scorecard");
const sensitivitiesSheet = workbook.worksheets.add("Sensitivities");
const readmeSheet = workbook.worksheets.add("ReadMe");

function styleHeader(sheet, address) {
  const header = sheet.getRange(address);
  header.format.fill = "accent1";
  header.format.font = { color: "lt1", bold: true };
  header.format.horizontalAlignment = "center";
  header.format.wrapText = true;
  header.format.rowHeightPx = 28;
}

function currencyRange(sheet, address) {
  sheet.getRange(address).format.numberFormat = '"$"#,##0;[Red]-"$"#,##0';
}

const proposal = committee.proposal;

summarySheet.getRange("A1:H1").values = [["Investment Committee Scorecard", null, null, null, null, null, null, null]];
summarySheet.getRange("A1:H1").format.fill = "accent1";
summarySheet.getRange("A1:H1").format.font = { color: "lt1", bold: true, size: 18 };
summarySheet.getRange("A3:B8").values = [
  ["Proposal", proposal.title],
  ["Company", proposal.company],
  ["Type", proposal.proposal_type],
  ["Recommendation", committee.recommendation],
  ["Total Score", committee.total_score],
  ["Sponsor", proposal.sponsor],
];
summarySheet.getRange("D3:E9").values = [
  ["Investment", proposal.investment_amount_usd],
  ["Annual Revenue Uplift", proposal.annual_revenue_uplift_usd],
  ["Annual Cost Savings", proposal.annual_cost_savings_usd],
  ["NPV", proposal.npv_usd],
  ["IRR", proposal.irr_pct],
  ["Payback Months", proposal.payback_months],
  ["Gross Margin %", proposal.gross_margin_pct],
];
summarySheet.getRange("A3:A8").format.font = { bold: true };
summarySheet.getRange("D3:D9").format.font = { bold: true };
currencyRange(summarySheet, "E3:E6");
summarySheet.getRange("E7:E7").format.numberFormat = "0.0%";
summarySheet.getRange("E8:E8").format.numberFormat = "0.0";
summarySheet.getRange("E9:E9").format.numberFormat = "0.0%";

styleHeader(summarySheet, "A11:B11");
summarySheet.getRange("A11:B11").values = [["Committee Notes", null]];
summarySheet.getRange(`A12:B${11 + committee.committee_notes.length}`).values = committee.committee_notes.map((item) => [item, null]);
summarySheet.getRange(`A12:B${11 + committee.committee_notes.length}`).format.wrapText = true;
summarySheet.getRange(`A12:B${11 + committee.committee_notes.length}`).format.rowHeightPx = 30;

summarySheet.charts.add("bar", {
  title: "Weighted Scorecard",
  categories: committee.scorecard.map((item) => item.name),
  series: [{ name: "Weighted Score", values: committee.scorecard.map((item) => item.weighted_score) }],
  from: { row: 2, col: 6 },
  extent: { widthPx: 520, heightPx: 260 },
  hasLegend: false,
});

styleHeader(scorecardSheet, "A1:E1");
scorecardSheet.getRange("A1:E1").values = [["Criterion", "Score", "Weight", "Weighted Score", "Rationale"]];
scorecardSheet.getRange(`A2:E${1 + committee.scorecard.length}`).values = committee.scorecard.map((item) => [
  item.name,
  item.score,
  item.weight,
  item.weighted_score,
  item.rationale,
]);
scorecardSheet.getRange(`C2:C${1 + committee.scorecard.length}`).format.numberFormat = "0%";
scorecardSheet.getRange(`A2:E${1 + committee.scorecard.length}`).format.wrapText = true;
scorecardSheet.freezePanes.freezeRows(1);
scorecardSheet.getRange("A:E").format.columnWidthPx = 150;

styleHeader(sensitivitiesSheet, "A1:B1");
sensitivitiesSheet.getRange("A1:B1").values = [["Sensitivity", "Value"]];
sensitivitiesSheet.getRange("A2:B5").values = [
  ["LTV/CAC Ratio", committee.sensitivities.ltv_cac_ratio],
  ["Annual Value / Investment", committee.sensitivities.annual_value_vs_investment],
  ["Downside Case Score", committee.sensitivities.downside_case_score],
  ["Upside Case Score", committee.sensitivities.upside_case_score],
];
styleHeader(sensitivitiesSheet, "D1:E1");
sensitivitiesSheet.getRange("D1:E1").values = [["Evidence Gaps", null]];
const evidenceGaps = committee.evidence_gaps.length ? committee.evidence_gaps : ["None identified"];
sensitivitiesSheet.getRange(`D2:E${1 + evidenceGaps.length}`).values = evidenceGaps.map((item) => [item, null]);
sensitivitiesSheet.getRange(`D2:E${1 + evidenceGaps.length}`).format.wrapText = true;
sensitivitiesSheet.getRange(`D2:E${1 + evidenceGaps.length}`).format.rowHeightPx = 30;
sensitivitiesSheet.getRange("A:E").format.columnWidthPx = 170;

readmeSheet.getRange("A1:D1").values = [["How To Use This Scorecard", null, null, null]];
readmeSheet.getRange("A1:D1").format.fill = "accent1";
readmeSheet.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 16 };
readmeSheet.getRange("A3:A8").values = [
  ["1. Review Summary for the recommendation tier and the core return profile."],
  ["2. Use Scorecard to challenge the weighted logic and committee rationale."],
  ["3. Use Sensitivities to see whether the recommendation is robust to weaker assumptions."],
  ["4. Do not treat this workbook as a substitute for full diligence or legal review."],
  ["CHP Session Summary"],
  [sessionSummary],
];
readmeSheet.getRange("A3:A8").format.wrapText = true;
readmeSheet.getRange("A3:A8").format.rowHeightPx = 34;
readmeSheet.getRange("A:D").format.columnWidthPx = 180;

await workbook.render({ sheetName: "Summary", range: "A1:M28", scale: 1.3 });
await workbook.render({ sheetName: "Scorecard", range: "A1:E12", scale: 1.2 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
