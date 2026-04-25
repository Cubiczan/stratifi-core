import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: build_ap_optimizer_workbook.mjs <input.json> <output.xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { optimizer, session_summary: sessionSummary } = payload;
const workbook = Workbook.create();

const overview = workbook.worksheets.add("Overview");
const payments = workbook.worksheets.add("Recommended_Payments");
const deferred = workbook.worksheets.add("Deferred_Invoices");
const vendors = workbook.worksheets.add("Vendor_View");
const readme = workbook.worksheets.add("ReadMe");

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

overview.getRange("A1:H1").values = [["AP Cash & Payables Optimizer", null, null, null, null, null, null, null]];
overview.getRange("A1:H1").format.fill = "accent1";
overview.getRange("A1:H1").format.font = { color: "lt1", bold: true, size: 18 };

const recommendedCash = optimizer.recommended_payments.reduce((sum, item) => sum + item.amount, 0);
const deferredCash = optimizer.deferred_invoices.reduce((sum, item) => sum + item.amount, 0);

overview.getRange("A3:B7").values = [
  ["As Of", optimizer.as_of_date],
  ["Cash Available", optimizer.cash_available],
  ["Recommended Cash", recommendedCash],
  ["Deferred Cash", deferredCash],
  ["Strategic Vendors", optimizer.strategic_vendors.join(", ") || "None"],
];
overview.getRange("D3:E7").values = [
  ["Max Vendors", optimizer.max_vendors],
  ["Avoid Overdue", optimizer.avoid_overdue ? "Yes" : "No"],
  ["Warnings", optimizer.warnings.length],
  ["Negotiation Targets", optimizer.negotiation_targets.length],
  ["Questions Needed", optimizer.questions_needed.length],
];
overview.getRange("A3:A7").format.font = { bold: true };
overview.getRange("D3:D7").format.font = { bold: true };
currencyRange(overview, "B4:B5");
currencyRange(overview, "B6:B6");

styleHeader(overview, "A9:B9");
overview.getRange("A9:B9").values = [["Warnings", null]];
overview.getRange(`A10:B${9 + Math.max(1, optimizer.warnings.length)}`).values = (optimizer.warnings.length ? optimizer.warnings : ["No warnings."]).map((item) => [item, null]);
overview.getRange(`A10:B${9 + Math.max(1, optimizer.warnings.length)}`).format.wrapText = true;

styleHeader(overview, "D9:E9");
overview.getRange("D9:E9").values = [["Aging Buckets", null]];
overview.getRange(`D10:E${9 + optimizer.aging_buckets.length}`).values = optimizer.aging_buckets.map((item) => [item.label, item.amount]);
currencyRange(overview, `E10:E${9 + optimizer.aging_buckets.length}`);

overview.charts.add("bar", {
  title: "Aging by Bucket",
  categories: optimizer.aging_buckets.map((item) => item.label),
  series: [{ name: "Open Balance", values: optimizer.aging_buckets.map((item) => item.amount), fill: "#153B5C" }],
  hasLegend: false,
  dataLabels: { showValue: false },
  barOptions: { direction: "column", grouping: "clustered", gapWidth: 80 },
  from: { row: 1, col: 7 },
  extent: { widthPx: 500, heightPx: 240 },
});
overview.charts.add("line", {
  title: "Due Outflow Next 6 Weeks",
  categories: optimizer.weekly_due_outflow.map((item) => item.week_label),
  series: [{ name: "Due Cash Out", values: optimizer.weekly_due_outflow.map((item) => item.amount), fill: "#C86A3B" }],
  hasLegend: false,
  dataLabels: { showValue: false },
  lineOptions: { grouping: "standard", smooth: false },
  from: { row: 13, col: 7 },
  extent: { widthPx: 500, heightPx: 240 },
});

styleHeader(payments, "A1:G1");
payments.getRange("A1:G1").values = [[
  "Invoice ID",
  "Vendor",
  "Pay Date",
  "Amount",
  "Priority Score",
  "Overdue Risk",
  "Rationale",
]];
payments.getRange(`A2:G${1 + optimizer.recommended_payments.length}`).values = optimizer.recommended_payments.map((item) => [
  item.invoice_id,
  item.vendor,
  item.pay_date,
  item.amount,
  item.priority_score,
  item.overdue_risk,
  item.rationale,
]);
currencyRange(payments, `D2:D${1 + optimizer.recommended_payments.length}`);
payments.freezePanes.freezeRows(1);
payments.getRange("A:G").format.columnWidthPx = 130;

styleHeader(deferred, "A1:E1");
deferred.getRange("A1:E1").values = [[
  "Invoice ID",
  "Vendor",
  "Amount",
  "Risk Level",
  "Defer Reason",
]];
deferred.getRange(`A2:E${1 + optimizer.deferred_invoices.length}`).values = optimizer.deferred_invoices.map((item) => [
  item.invoice_id,
  item.vendor,
  item.amount,
  item.risk_level,
  item.defer_reason,
]);
currencyRange(deferred, `C2:C${1 + optimizer.deferred_invoices.length}`);
deferred.freezePanes.freezeRows(1);
deferred.getRange("A:E").format.columnWidthPx = 150;

styleHeader(vendors, "A1:D1");
vendors.getRange("A1:D1").values = [[
  "Vendor",
  "Open Balance",
  "Cumulative %",
  "Suggested Move",
]];
const vendorRows = optimizer.vendor_concentration.map((item) => {
  const match = optimizer.negotiation_targets.find((target) => target.vendor === item.vendor);
  return [item.vendor, item.open_balance, item.cumulative_pct, match ? match.suggested_move : "Monitor"];
});
vendors.getRange(`A2:D${1 + vendorRows.length}`).values = vendorRows;
currencyRange(vendors, `B2:B${1 + vendorRows.length}`);
vendors.getRange(`C2:C${1 + vendorRows.length}`).format.numberFormat = "0.0%";
vendors.freezePanes.freezeRows(1);
vendors.getRange("A:D").format.columnWidthPx = 160;

readme.getRange("A1:D1").values = [["How To Use This Workbook", null, null, null]];
readme.getRange("A1:D1").format.fill = "accent1";
readme.getRange("A1:D1").format.font = { color: "lt1", bold: true, size: 16 };
readme.getRange("A3:A9").values = [
  ["1. Start on Overview for cash usage, aging exposure, and due-outflow pressure."],
  ["2. Use Recommended_Payments as the proposed weekly payment set under the current cash cap."],
  ["3. Use Deferred_Invoices to review what risk is being pushed into the next cycle."],
  ["4. Use Vendor_View to identify concentration and negotiation candidates."],
  ["5. Treat strategic-vendor exceptions and missing due-date invoices as manual review items."],
  ["CHP Session Summary"],
  [sessionSummary],
];
readme.getRange("A3:A9").format.wrapText = true;
readme.getRange("A3:A9").format.rowHeightPx = 34;
readme.getRange("A:D").format.columnWidthPx = 180;

await workbook.render({ sheetName: "Overview", range: "A1:O28", scale: 1.5 });
await workbook.render({ sheetName: "Recommended_Payments", range: "A1:G18", scale: 1.2 });

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
