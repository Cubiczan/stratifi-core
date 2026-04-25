import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_saas_operating_model_workbook.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { model, session_summary: sessionSummary } = payload;
const workbook = Workbook.create();

const summarySheet = workbook.worksheets.add("Summary");
const monthlySheet = workbook.worksheets.add("Monthly_Model");
const driversSheet = workbook.worksheets.add("Drivers");
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

summarySheet.getRange("A1:H1").values = [["24-Month SaaS Operating Model", null, null, null, null, null, null, null]];
summarySheet.getRange("A1:H1").format.fill = "accent1";
summarySheet.getRange("A1:H1").format.font = { color: "lt1", bold: true, size: 18 };

const rows = model.monthly_rows;
const minCash = Math.min(...rows.map((row) => row.closing_cash));
const maxMrr = Math.max(...rows.map((row) => row.mrr));
const month24 = rows[rows.length - 1];

summarySheet.getRange("A3:B7").values = [
  ["Company", model.assumptions.company_name],
  ["Opening Cash", model.assumptions.opening_cash_usd],
  ["Current Customers", model.assumptions.current_customers],
  ["Current ARPA", model.assumptions.current_arpa],
  ["Gross Margin %", model.assumptions.gross_margin_pct],
];
summarySheet.getRange("D3:E7").values = [
  ["Lowest Cash", minCash],
  ["Peak MRR", maxMrr],
  ["Month 24 Cash", month24.closing_cash],
  ["Month 24 Headcount", month24.headcount],
  ["Fundraise Month", model.assumptions.fundraise_month_number],
];
summarySheet.getRange("A3:A7").format.font = { bold: true };
summarySheet.getRange("D3:D7").format.font = { bold: true };
currencyRange(summarySheet, "B4:B5");
summarySheet.getRange("B7:B7").format.numberFormat = "0.0%";
currencyRange(summarySheet, "E3:E5");

styleHeader(summarySheet, "A9:B9");
summarySheet.getRange("A9:B9").values = [["Key Findings", null]];
summarySheet.getRange(`A10:B${9 + model.key_findings.length}`).values = model.key_findings.map((item) => [item, null]);
summarySheet.getRange(`A10:B${9 + model.key_findings.length}`).format.wrapText = true;
summarySheet.getRange(`A10:B${9 + model.key_findings.length}`).format.rowHeightPx = 28;

summarySheet.charts.add("line", {
  title: "Cash Balance",
  categories: rows.map((row) => row.label),
  series: [{ name: "Closing Cash", values: rows.map((row) => row.closing_cash) }],
  hasLegend: false,
  dataLabels: { showValue: false },
  from: { row: 1, col: 6 },
  extent: { widthPx: 520, heightPx: 240 },
});
summarySheet.charts.add("line", {
  title: "MRR",
  categories: rows.map((row) => row.label),
  series: [{ name: "MRR", values: rows.map((row) => row.mrr) }],
  hasLegend: false,
  dataLabels: { showValue: false },
  from: { row: 14, col: 6 },
  extent: { widthPx: 520, heightPx: 240 },
});

styleHeader(monthlySheet, "A1:Q1");
monthlySheet.getRange("A1:Q1").values = [[
  "Month",
  "Customers Start",
  "New Customers",
  "Churned Customers",
  "Customers End",
  "Churn %",
  "ARPA",
  "MRR",
  "Revenue",
  "Gross Profit",
  "Headcount",
  "Hires",
  "Opex",
  "EBITDA",
  "Fundraise",
  "Opening Cash",
  "Closing Cash",
]];
monthlySheet.getRange(`A2:Q${1 + rows.length}`).values = rows.map((row) => [
  row.label,
  row.customers_start,
  row.new_customers,
  row.churned_customers,
  row.customers_end,
  row.churn_pct,
  row.arpa,
  row.mrr,
  row.revenue,
  row.gross_profit,
  row.headcount,
  row.hires,
  row.opex,
  row.ebitda,
  row.fundraise_usd,
  row.opening_cash,
  row.closing_cash,
]);
monthlySheet.getRange(`F2:F${1 + rows.length}`).format.numberFormat = "0.0%";
currencyRange(monthlySheet, `G2:Q${1 + rows.length}`);
monthlySheet.freezePanes.freezeRows(1);
monthlySheet.getRange("A:Q").format.columnWidthPx = 110;

styleHeader(driversSheet, "A1:F1");
driversSheet.getRange("A1:F1").values = [[
  "Month",
  "New Customers",
  "Churn %",
  "ARPA",
  "Hires",
  "Fundraise",
]];
driversSheet.getRange(`A2:F${1 + model.driver_forecast.length}`).values = model.driver_forecast.map((row) => [
  row.label,
  row.new_customers,
  row.churn_pct,
  row.arpa,
  row.hires,
  row.fundraise_usd,
]);
driversSheet.getRange(`C2:C${1 + model.driver_forecast.length}`).format.numberFormat = "0.0%";
currencyRange(driversSheet, `D2:F${1 + model.driver_forecast.length}`);
driversSheet.freezePanes.freezeRows(1);
driversSheet.getRange("A:F").format.columnWidthPx = 120;

readmeSheet.getRange("A1:D1").values = [["How To Use This Model", null, null, null]];
readmeSheet.getRange("A1:D1").format.fill = "accent1";
readmeSheet.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 16 };
readmeSheet.getRange("A3:A8").values = [
  ["1. Start on Summary for the cash and MRR trajectory."],
  ["2. Use Drivers to inspect the acquisition, churn, ARPA, hiring, and fundraise assumptions."],
  ["3. Use Monthly_Model for the detailed EBITDA and cash bridge."],
  ["4. Treat this as a driver-based planning model, not a locked base case, until the CHP findings are resolved."],
  ["CHP Session Summary"],
  [sessionSummary],
];
readmeSheet.getRange("A3:A8").format.wrapText = true;
readmeSheet.getRange("A3:A8").format.rowHeightPx = 34;
readmeSheet.getRange("A:D").format.columnWidthPx = 180;

await workbook.render({ sheetName: "Summary", range: "A1:N28", scale: 1.5 });
await workbook.render({ sheetName: "Monthly_Model", range: "A1:Q18", scale: 1.2 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
