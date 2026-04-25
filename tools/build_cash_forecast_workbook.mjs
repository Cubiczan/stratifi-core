import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_cash_forecast_workbook.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { forecast, session_summary: sessionSummary } = payload;

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Weekly_Summary");
const inflowSheet = workbook.worksheets.add("Inflows_By_Week");
const outflowSheet = workbook.worksheets.add("Outflows_By_Week");
const driversSheet = workbook.worksheets.add("Drivers");
const readmeSheet = workbook.worksheets.add("ReadMe");

const weeklySummary = forecast.weekly_summary;
const inflows = forecast.inflows_by_week;
const outflows = forecast.outflows_by_week;
const drivers = forecast.driver_details;
const riskFlags = forecast.risk_flags;

function asDate(value) {
  return new Date(`${value}T00:00:00`);
}

function currencyRange(sheet, address) {
  sheet.getRange(address).format.numberFormat = '"$"#,##0;[Red]-"$"#,##0';
}

function styleHeader(sheet, address) {
  const header = sheet.getRange(address);
  header.format.fill = "accent1";
  header.format.font = { color: "lt1", bold: true };
  header.format.horizontalAlignment = "center";
  header.format.wrapText = true;
  header.format.rowHeightPx = 28;
}

summarySheet.getRange("A1:G1").values = [["13-Week Cash Forecast Engine", null, null, null, null, null, null]];
summarySheet.getRange("A1:G1").format.fill = "accent1";
summarySheet.getRange("A1:G1").format.font = { color: "lt1", bold: true, size: 18 };
summarySheet.getRange("A1:G1").format.rowHeightPx = 30;

const redWeeks = weeklySummary.filter((row) => row.risk_flag !== "OK").length;
const minClosing = Math.min(...weeklySummary.map((row) => row.closing_balance));
const maxOutflow = Math.max(...weeklySummary.map((row) => row.cash_out));

summarySheet.getRange("A3:B6").values = [
  ["As Of Date", asDate(forecast.settings.as_of_date)],
  ["Opening Cash", forecast.opening_cash_total],
  ["Minimum Closing Cash", minClosing],
  ["Weeks Flagged", redWeeks],
];
summarySheet.getRange("D3:E6").values = [
  ["Minimum Cash Warning", forecast.settings.min_cash_warning],
  ["Horizon (Weeks)", forecast.settings.horizon_weeks],
  ["Jitter Assumption", forecast.settings.jitter_pct],
  ["Peak Weekly Outflow", maxOutflow],
];
summarySheet.getRange("A3:E6").format.rowHeightPx = 24;
summarySheet.getRange("A3:A6").format.font = { bold: true };
summarySheet.getRange("D3:D6").format.font = { bold: true };
summarySheet.getRange("B3:B3").format.numberFormat = "yyyy-mm-dd";
currencyRange(summarySheet, "B4:B5");
currencyRange(summarySheet, "E3:E3");
summarySheet.getRange("E5:E5").format.numberFormat = "0.0%";
currencyRange(summarySheet, "E6:E6");

styleHeader(summarySheet, "A8:G8");
summarySheet.getRange("A8:G8").values = [[
  "Week Ending",
  "Opening Balance",
  "Cash In",
  "Cash Out",
  "Net Cash Flow",
  "Closing Balance",
  "Risk Flag",
]];

const summaryRows = weeklySummary.map((row) => [
  asDate(row.week_ending),
  row.opening_balance,
  row.cash_in,
  row.cash_out,
  row.net_cash_flow,
  row.closing_balance,
  row.risk_flag,
]);
summarySheet.getRange(`A9:G${8 + summaryRows.length}`).values = summaryRows;
summarySheet.getRange(`A9:A${8 + summaryRows.length}`).format.numberFormat = "yyyy-mm-dd";
currencyRange(summarySheet, `B9:F${8 + summaryRows.length}`);
summarySheet.getRange(`A8:G${8 + summaryRows.length}`).format.rowHeightPx = 24;

weeklySummary.forEach((row, index) => {
  const excelRow = index + 9;
  if (row.risk_flag === "CRITICAL_NEGATIVE_CASH") {
    summarySheet.getRange(`A${excelRow}:G${excelRow}`).format.fill = "#FDECEC";
    summarySheet.getRange(`G${excelRow}:G${excelRow}`).format.font = { color: "#9F1239", bold: true };
  } else if (row.risk_flag === "LOW_CASH_WARNING") {
    summarySheet.getRange(`A${excelRow}:G${excelRow}`).format.fill = "#FFF7E6";
    summarySheet.getRange(`G${excelRow}:G${excelRow}`).format.font = { color: "#B45309", bold: true };
  }
});

summarySheet.getRange("I2:K2").values = [["Risk Notes", null, null]];
summarySheet.getRange("I2:K2").format.fill = "accent2";
summarySheet.getRange("I2:K2").format.font = { color: "lt1", bold: true };
summarySheet.getRange("I3:K8").values = (riskFlags.length ? riskFlags : ["No risk flags raised."]).map((item) => [item, null, null]);
summarySheet.getRange("I3:K8").format.wrapText = true;
summarySheet.getRange("I3:K8").format.rowHeightPx = 36;

summarySheet.charts.add("line", {
  title: "Closing Cash Balance by Week",
  categories: weeklySummary.map((row) => row.week_ending),
  series: [{ name: "Closing Cash", values: weeklySummary.map((row) => row.closing_balance) }],
  hasLegend: false,
  dataLabels: { showValue: false },
  from: { row: 1, col: 11 },
  extent: { widthPx: 620, heightPx: 280 },
});

summarySheet.freezePanes.freezeRows(8);
summarySheet.getRange("A:A").format.columnWidthPx = 110;
summarySheet.getRange("B:F").format.columnWidthPx = 115;
summarySheet.getRange("G:G").format.columnWidthPx = 155;
summarySheet.getRange("I:K").format.columnWidthPx = 180;

styleHeader(inflowSheet, "A1:C1");
inflowSheet.getRange("A1:C1").values = [["Week Ending", "Channel", "Cash In USD"]];
inflowSheet.getRange(`A2:C${1 + inflows.length}`).values = inflows.map((row) => [
  asDate(row.week_ending),
  row.channel,
  row.cash_in_usd,
]);
inflowSheet.getRange(`A2:A${1 + inflows.length}`).format.numberFormat = "yyyy-mm-dd";
currencyRange(inflowSheet, `C2:C${1 + inflows.length}`);
inflowSheet.freezePanes.freezeRows(1);
inflowSheet.getRange("A:A").format.columnWidthPx = 110;
inflowSheet.getRange("B:B").format.columnWidthPx = 160;
inflowSheet.getRange("C:C").format.columnWidthPx = 120;

styleHeader(outflowSheet, "A1:C1");
outflowSheet.getRange("A1:C1").values = [["Week Ending", "Category", "Cash Out USD"]];
outflowSheet.getRange(`A2:C${1 + outflows.length}`).values = outflows.map((row) => [
  asDate(row.week_ending),
  row.category,
  row.cash_out_usd,
]);
outflowSheet.getRange(`A2:A${1 + outflows.length}`).format.numberFormat = "yyyy-mm-dd";
currencyRange(outflowSheet, `C2:C${1 + outflows.length}`);
outflowSheet.freezePanes.freezeRows(1);
outflowSheet.getRange("A:A").format.columnWidthPx = 110;
outflowSheet.getRange("B:B").format.columnWidthPx = 170;
outflowSheet.getRange("C:C").format.columnWidthPx = 120;

styleHeader(driversSheet, "A1:E1");
driversSheet.getRange("A1:E1").values = [[
  "Channel",
  "Baseline Cash In",
  "Trend %",
  "Seasonality",
  "Jitter %",
]];
driversSheet.getRange(`A2:E${1 + drivers.length}`).values = drivers.map((row) => [
  row.channel,
  row.baseline,
  row.trend_pct,
  row.seasonality_multiplier,
  row.jitter_pct,
]);
currencyRange(driversSheet, `B2:B${1 + drivers.length}`);
driversSheet.getRange(`C2:E${1 + drivers.length}`).format.numberFormat = "0.0%";
driversSheet.freezePanes.freezeRows(1);
driversSheet.getRange("A:A").format.columnWidthPx = 150;
driversSheet.getRange("B:E").format.columnWidthPx = 120;

readmeSheet.getRange("A1:D1").values = [["How To Use This Workbook", null, null, null]];
readmeSheet.getRange("A1:D1").format.fill = "accent1";
readmeSheet.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 16 };
readmeSheet.getRange("A3:A9").values = [
  ["1. Review Weekly_Summary first for flagged weeks and balance trajectory."],
  ["2. Use Inflows_By_Week and Outflows_By_Week to inspect the timing drivers behind each week."],
  ["3. Review Drivers for the trailing baseline, trend, seasonality, and jitter assumptions applied."],
  ["4. Treat LOW_CASH_WARNING as an action queue and CRITICAL_NEGATIVE_CASH as an escalation event."],
  ["5. Use the CHP session summary below when preparing a finance review or partner-model challenge."],
  [null],
  ["CHP Session Summary"],
];
readmeSheet.getRange("A3:A9").format.wrapText = true;
readmeSheet.getRange("A3:A9").format.rowHeightPx = 34;
readmeSheet.getRange("A9:A9").format.font = { bold: true };
readmeSheet.getRange("A10:D32").values = [[sessionSummary, null, null, null]];
readmeSheet.getRange("A10:D32").format.wrapText = true;
readmeSheet.getRange("A10:D32").format.rowHeightPx = 22;
readmeSheet.getRange("A:D").format.columnWidthPx = 180;

await workbook.inspect({
  kind: "table",
  range: "Weekly_Summary!A1:G21",
  include: "values,formulas",
  tableMaxRows: 21,
  tableMaxCols: 7,
});
await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
await workbook.render({ sheetName: "Weekly_Summary", range: "A1:P24", scale: 1.5 });
await workbook.render({ sheetName: "ReadMe", range: "A1:D24", scale: 1.5 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
