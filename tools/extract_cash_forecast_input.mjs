import fs from "node:fs/promises";
import path from "node:path";

import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  throw new Error("Usage: extract_cash_forecast_input.mjs <input.xlsx> <output.json>");
}

function excelSerialToIso(value) {
  const millis = Math.round((value - 25569) * 86400 * 1000);
  return new Date(millis).toISOString().slice(0, 10);
}

function normalizeDate(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "number") {
    return excelSerialToIso(value);
  }
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  return String(value).slice(0, 10);
}

function normalizeNumber(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  if (typeof value === "number") {
    return value;
  }
  return Number(String(value).replace(/,/g, "").trim());
}

function normalizeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

const file = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(file);

async function table(sheet, range, rows, cols) {
  const inspected = await workbook.inspect({
    kind: "table",
    range: `${sheet}!${range}`,
    include: "values",
    tableMaxRows: rows,
    tableMaxCols: cols,
  });
  const parsed = JSON.parse(inspected.ndjson);
  return parsed.values || [];
}

// Large inspect windows can collapse unexpectedly on import, so keep these
// ranges comfortably above normal finance volumes without crossing that edge.
const opening = await table("Opening_Cash", "A1:B200", 200, 2);
const settings = await table("Settings", "A1:B20", 20, 2);
const sales = await table("Sales", "A1:C400", 400, 3);
const ap = await table("AP", "A1:D400", 400, 4);
const payroll = await table("Payroll", "A1:B250", 250, 2);
const outflows = await table("Outflows", "A1:E400", 400, 5);

function nonEmptyRow(row) {
  return row.some((value) => value !== null && value !== undefined && String(value).trim() !== "");
}

const settingsMap = Object.fromEntries(
  settings.slice(1).filter(nonEmptyRow).map(([key, value]) => [normalizeText(key), value]),
);

const payload = {
  opening_cash: opening.slice(1).filter(nonEmptyRow).map(([account, amount]) => ({
    account: normalizeText(account),
    amount_usd: normalizeNumber(amount),
  })),
  settings: {
    as_of_date: normalizeDate(settingsMap.AsOfDate),
    horizon_weeks: normalizeNumber(settingsMap.HorizonWeeks || 13),
    jitter_pct: normalizeNumber(settingsMap.JitterPct || 0),
    min_cash_warning: normalizeNumber(settingsMap.MinCashWarning || 0),
  },
  sales: sales.slice(1).filter(nonEmptyRow).map(([rowDate, channel, amount]) => ({
    date: normalizeDate(rowDate),
    channel: normalizeText(channel),
    amount_usd: normalizeNumber(amount),
  })),
  ap_rows: ap.slice(1).filter(nonEmptyRow).map(([rowDate, vendor, category, amount]) => ({
    date: normalizeDate(rowDate),
    vendor: normalizeText(vendor),
    category: normalizeText(category),
    amount_usd: normalizeNumber(amount),
  })),
  payroll_rows: payroll.slice(1).filter(nonEmptyRow).map(([rowDate, amount]) => ({
    date: normalizeDate(rowDate),
    amount_usd: normalizeNumber(amount),
  })),
  outflow_rows: outflows.slice(1).filter(nonEmptyRow).map(([rowDate, category, vendor, amount, type]) => ({
    date: normalizeDate(rowDate),
    category: normalizeText(category),
    vendor: normalizeText(vendor),
    amount_usd: normalizeNumber(amount),
    type: normalizeText(type),
  })),
};

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, JSON.stringify(payload, null, 2));
