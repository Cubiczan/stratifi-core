import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_saas_kpi_dashboard_workbook.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { dashboard, session_summary: sessionSummary } = payload;
const workbook = Workbook.create();

const dashboardSheet = workbook.worksheets.add("Dashboard");
const monthlySheet = workbook.worksheets.add("Monthly_Data");
const varianceSheet = workbook.worksheets.add("Variance_Table");
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

const months = dashboard.months;
const latest = months[months.length - 1];

dashboardSheet.getRange("A1:H1").values = [["SaaS KPI Dashboard", null, null, null, null, null, null, null]];
dashboardSheet.getRange("A1:H1").format.fill = "accent1";
dashboardSheet.getRange("A1:H1").format.font = { color: "lt1", bold: true, size: 18 };
dashboardSheet.getRange("A3:B6").values = [
  ["Latest Month", latest.month],
  ["Revenue", latest.actuals.Revenue],
  ["MRR", latest.actuals.MRR],
  ["Rule of 40", latest.actuals["Rule of 40"]],
];
dashboardSheet.getRange("D3:E6").values = [
  ["EBITDA", latest.actuals.EBITDA],
  ["EBITDA Margin", latest.actuals["EBITDA Margin"]],
  ["Gross Margin %", latest.actuals["Gross Margin %"]],
  ["ARR", latest.actuals.ARR],
];
dashboardSheet.getRange("A3:A6").format.font = { bold: true };
dashboardSheet.getRange("D3:D6").format.font = { bold: true };
currencyRange(dashboardSheet, "B4:B5");
dashboardSheet.getRange("B6:B6").format.numberFormat = "0.0%";
currencyRange(dashboardSheet, "E3:E3");
dashboardSheet.getRange("E4:E5").format.numberFormat = "0.0%";
currencyRange(dashboardSheet, "E6:E6");

styleHeader(dashboardSheet, "A8:E8");
dashboardSheet.getRange("A8:E8").values = [["Key Metric", "Actual", "Budget", "Variance", "Variance %"]];
dashboardSheet.getRange(`A9:E${8 + dashboard.kpis.length}`).values = dashboard.kpis.map((item) => [
  item.name,
  item.actual,
  item.budget,
  item.variance,
  item.variance_pct,
]);
currencyRange(dashboardSheet, `B9:D${8 + dashboard.kpis.length}`);
dashboardSheet.getRange(`E9:E${8 + dashboard.kpis.length}`).format.numberFormat = "0.0%";

styleHeader(dashboardSheet, "G8:H8");
dashboardSheet.getRange("G8:H8").values = [["Key Findings", null]];
dashboardSheet.getRange(`G9:H${8 + dashboard.key_findings.length}`).values = dashboard.key_findings.map((item) => [item, null]);
dashboardSheet.getRange(`G9:H${8 + dashboard.key_findings.length}`).format.wrapText = true;
dashboardSheet.getRange(`G9:H${8 + dashboard.key_findings.length}`).format.rowHeightPx = 30;

dashboardSheet.charts.add("line", {
  title: "MRR Actual vs Budget",
  categories: months.map((row) => row.month),
  series: [
    { name: "Actual", values: months.map((row) => row.actuals.MRR) },
    { name: "Budget", values: months.map((row) => row.budget.MRR) },
  ],
  from: { row: 1, col: 9 },
  extent: { widthPx: 520, heightPx: 220 },
});
dashboardSheet.charts.add("line", {
  title: "Revenue vs OpEx",
  categories: months.map((row) => row.month),
  series: [
    { name: "Revenue", values: months.map((row) => row.actuals.Revenue) },
    { name: "OpEx", values: months.map((row) => row.actuals.OpEx) },
  ],
  from: { row: 14, col: 9 },
  extent: { widthPx: 520, heightPx: 220 },
});

styleHeader(monthlySheet, "A1:U1");
monthlySheet.getRange("A1:U1").values = [[
  "Month",
  "MRR Actual",
  "MRR Budget",
  "ARR Actual",
  "ARR Budget",
  "Revenue Actual",
  "Revenue Budget",
  "COGS Actual",
  "COGS Budget",
  "OpEx Actual",
  "OpEx Budget",
  "EBITDA Actual",
  "EBITDA Budget",
  "EBITDA Margin Actual",
  "EBITDA Margin Budget",
  "Gross Margin % Actual",
  "Gross Margin % Budget",
  "CAC Actual",
  "CAC Budget",
  "LTV Actual",
  "LTV Budget",
]];
monthlySheet.getRange(`A2:U${1 + months.length}`).values = months.map((row) => [
  row.month,
  row.actuals.MRR,
  row.budget.MRR,
  row.actuals.ARR,
  row.budget.ARR,
  row.actuals.Revenue,
  row.budget.Revenue,
  row.actuals.COGS,
  row.budget.COGS,
  row.actuals.OpEx,
  row.budget.OpEx,
  row.actuals.EBITDA,
  row.budget.EBITDA,
  row.actuals["EBITDA Margin"],
  row.budget["EBITDA Margin"],
  row.actuals["Gross Margin %"],
  row.budget["Gross Margin %"],
  row.actuals.CAC,
  row.budget.CAC,
  row.actuals.LTV,
  row.budget.LTV,
]);
currencyRange(monthlySheet, `B2:M${1 + months.length}`);
monthlySheet.getRange(`N2:Q${1 + months.length}`).format.numberFormat = "0.0%";
currencyRange(monthlySheet, `R2:U${1 + months.length}`);
monthlySheet.freezePanes.freezeRows(1);
monthlySheet.getRange("A:U").format.columnWidthPx = 118;

styleHeader(varianceSheet, "A1:E1");
varianceSheet.getRange("A1:E1").values = [["Metric", "Actual", "Budget", "Variance", "Variance %"]];
varianceSheet.getRange(`A2:E${1 + dashboard.variance_rows.length}`).values = dashboard.variance_rows.map((row) => [
  row.metric,
  row.actual,
  row.budget,
  row.variance,
  row.variance_pct,
]);
currencyRange(varianceSheet, `B2:D${1 + dashboard.variance_rows.length}`);
varianceSheet.getRange(`E2:E${1 + dashboard.variance_rows.length}`).format.numberFormat = "0.0%";
varianceSheet.freezePanes.freezeRows(1);
varianceSheet.getRange("A:E").format.columnWidthPx = 130;

readmeSheet.getRange("A1:D1").values = [["How To Use This Dashboard", null, null, null]];
readmeSheet.getRange("A1:D1").format.fill = "accent1";
readmeSheet.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 16 };
readmeSheet.getRange("A3:A8").values = [
  ["1. Start on Dashboard for the board-facing KPI surface."],
  ["2. Use Monthly_Data to audit actual versus budget values across the reporting period."],
  ["3. Use Variance_Table to see which metrics are moving the executive narrative."],
  ["4. Refresh this workbook only after confirming KPI definitions still match across actuals and budget sources."],
  ["CHP Session Summary"],
  [sessionSummary],
];
readmeSheet.getRange("A3:A8").format.wrapText = true;
readmeSheet.getRange("A3:A8").format.rowHeightPx = 34;
readmeSheet.getRange("A:D").format.columnWidthPx = 180;

await workbook.render({ sheetName: "Dashboard", range: "A1:P30", scale: 1.3 });
await workbook.render({ sheetName: "Monthly_Data", range: "A1:U16", scale: 1.1 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
