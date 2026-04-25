import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_cash_forecast_input_template.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();

const introSheet = workbook.worksheets.add("ReadMe");
const openingSheet = workbook.worksheets.add("Opening_Cash");
const settingsSheet = workbook.worksheets.add("Settings");
const salesSheet = workbook.worksheets.add("Sales");
const apSheet = workbook.worksheets.add("AP");
const payrollSheet = workbook.worksheets.add("Payroll");
const outflowsSheet = workbook.worksheets.add("Outflows");

function asDate(value) {
  return new Date(`${value}T00:00:00`);
}

function styleHeader(sheet, address) {
  const header = sheet.getRange(address);
  header.format.fill = "accent1";
  header.format.font = { color: "lt1", bold: true };
  header.format.horizontalAlignment = "center";
  header.format.wrapText = true;
  header.format.rowHeightPx = 28;
}

function styleSection(sheet, address, color = "accent2") {
  const header = sheet.getRange(address);
  header.format.fill = color;
  header.format.font = { color: "lt1", bold: true };
}

introSheet.getRange("A1:D1").values = [["13-Week Cash Forecast Input Workbook", null, null, null]];
introSheet.getRange("A1:D1").format.fill = "accent1";
introSheet.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 18 };
introSheet.getRange("A3:A10").values = [
  ["Use this workbook as the finance-owned input package for the 13-week cash forecast engine."],
  ["Sheet order is intentional: start with Settings, then Opening_Cash, then load transactional tabs."],
  ["Required tabs: Opening_Cash, Settings, Sales, AP, Payroll, Outflows."],
  ["Dates should stay in yyyy-mm-dd format."],
  ["Amounts are positive USD cash values."],
  ["Do not rename headers; append rows beneath the header line."],
  ["AP rows take precedence over matching Outflows rows during duplicate filtering."],
  ["Payroll always remains in the forecast, even if a similar outflow exists."],
];
introSheet.getRange("A3:A10").format.wrapText = true;
introSheet.getRange("A3:A10").format.rowHeightPx = 34;
introSheet.getRange("A:D").format.columnWidthPx = 180;

styleHeader(openingSheet, "A1:B1");
openingSheet.getRange("A1:B1").values = [["Account", "AmountUSD"]];
const openingRows = payload.opening_cash.length ? payload.opening_cash : [{ account: "Operating Account", amount_usd: 500000 }];
openingSheet.getRange(`A2:B${1 + openingRows.length}`).values = openingRows.map((row) => [row.account, row.amount_usd]);
openingSheet.getRange(`B2:B${1 + openingRows.length}`).format.numberFormat = '"$"#,##0';
openingSheet.getRange("A:B").format.columnWidthPx = 160;
openingSheet.freezePanes.freezeRows(1);

styleHeader(settingsSheet, "A1:B1");
settingsSheet.getRange("A1:B1").values = [["Key", "Value"]];
settingsSheet.getRange("A2:B5").values = [
  ["AsOfDate", asDate(payload.settings.as_of_date)],
  ["HorizonWeeks", payload.settings.horizon_weeks],
  ["JitterPct", payload.settings.jitter_pct],
  ["MinCashWarning", payload.settings.min_cash_warning],
];
settingsSheet.getRange("B2:B2").format.numberFormat = "yyyy-mm-dd";
settingsSheet.getRange("B4:B4").format.numberFormat = "0.0%";
settingsSheet.getRange("B5:B5").format.numberFormat = '"$"#,##0';
settingsSheet.getRange("A:B").format.columnWidthPx = 160;
settingsSheet.freezePanes.freezeRows(1);

styleHeader(salesSheet, "A1:C1");
salesSheet.getRange("A1:C1").values = [["Date", "Channel", "AmountUSD"]];
const salesRows = payload.sales.length
  ? payload.sales
  : [{ date: payload.settings.as_of_date, channel: "Online", amount_usd: 100000 }];
salesSheet.getRange(`A2:C${1 + salesRows.length}`).values = salesRows.map((row) => [
  asDate(row.date),
  row.channel,
  row.amount_usd,
]);
salesSheet.getRange(`A2:A${1 + salesRows.length}`).format.numberFormat = "yyyy-mm-dd";
salesSheet.getRange(`C2:C${1 + salesRows.length}`).format.numberFormat = '"$"#,##0';
salesSheet.getRange("A:C").format.columnWidthPx = 150;
salesSheet.freezePanes.freezeRows(1);

styleHeader(apSheet, "A1:D1");
apSheet.getRange("A1:D1").values = [["Date", "Vendor", "Category", "AmountUSD"]];
const apRows = payload.ap_rows.length
  ? payload.ap_rows
  : [{ date: payload.settings.as_of_date, vendor: "Vendor Name", category: "Software", amount_usd: 50000 }];
apSheet.getRange(`A2:D${1 + apRows.length}`).values = apRows.map((row) => [
  asDate(row.date),
  row.vendor,
  row.category,
  row.amount_usd,
]);
apSheet.getRange(`A2:A${1 + apRows.length}`).format.numberFormat = "yyyy-mm-dd";
apSheet.getRange(`D2:D${1 + apRows.length}`).format.numberFormat = '"$"#,##0';
apSheet.getRange("A:D").format.columnWidthPx = 150;
apSheet.freezePanes.freezeRows(1);

styleHeader(payrollSheet, "A1:B1");
payrollSheet.getRange("A1:B1").values = [["Date", "AmountUSD"]];
const payrollRows = payload.payroll_rows.length
  ? payload.payroll_rows
  : [{ date: payload.settings.as_of_date, amount_usd: 75000 }];
payrollSheet.getRange(`A2:B${1 + payrollRows.length}`).values = payrollRows.map((row) => [
  asDate(row.date),
  row.amount_usd,
]);
payrollSheet.getRange(`A2:A${1 + payrollRows.length}`).format.numberFormat = "yyyy-mm-dd";
payrollSheet.getRange(`B2:B${1 + payrollRows.length}`).format.numberFormat = '"$"#,##0';
payrollSheet.getRange("A:B").format.columnWidthPx = 150;
payrollSheet.freezePanes.freezeRows(1);

styleHeader(outflowsSheet, "A1:E1");
outflowsSheet.getRange("A1:E1").values = [["Date", "Category", "Vendor", "AmountUSD", "Type"]];
const outflowRows = payload.outflow_rows.length
  ? payload.outflow_rows
  : [{ date: payload.settings.as_of_date, category: "Hosting", vendor: "Cloud Co", amount_usd: 25000, type: "Recurring" }];
outflowsSheet.getRange(`A2:E${1 + outflowRows.length}`).values = outflowRows.map((row) => [
  asDate(row.date),
  row.category,
  row.vendor,
  row.amount_usd,
  row.type,
]);
outflowsSheet.getRange(`A2:A${1 + outflowRows.length}`).format.numberFormat = "yyyy-mm-dd";
outflowsSheet.getRange(`D2:D${1 + outflowRows.length}`).format.numberFormat = '"$"#,##0';
outflowsSheet.getRange("A:E").format.columnWidthPx = 145;
outflowsSheet.freezePanes.freezeRows(1);

styleSection(introSheet, "F2:H2");
introSheet.getRange("F2:H2").values = [["Expected Headers", null, null]];
introSheet.getRange("F3:H8").values = [
  ["Opening_Cash", "Account", "AmountUSD"],
  ["Settings", "Key", "Value"],
  ["Sales", "Date", "Channel / AmountUSD"],
  ["AP", "Date", "Vendor / Category / AmountUSD"],
  ["Payroll", "Date", "AmountUSD"],
  ["Outflows", "Date", "Category / Vendor / AmountUSD / Type"],
];
introSheet.getRange("F:H").format.columnWidthPx = 180;

await workbook.render({ sheetName: "ReadMe", range: "A1:H16", scale: 1.5 });
await workbook.render({ sheetName: "Sales", range: "A1:C12", scale: 1.5 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
