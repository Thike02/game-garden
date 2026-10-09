import assert from "node:assert/strict";
import { test } from "node:test";
import { formatPrice, timeWeightedAverage } from "./pricing.ts";

test("prices carry forward until the next change", () => {
  const points = [
    { day: "2026-01-01", price: 2300 },
    { day: "2026-01-07", price: 1150 },
  ];
  assert.equal(timeWeightedAverage(points, "2026-01-10", 10), (2300 * 6 + 1150 * 4) / 10);
});

test("matches the collector on the Patrick's Parabox history", () => {
  const points = [
    ["2025-09-01", 2300],
    ["2025-12-19", 1150],
    ["2026-01-06", 2300],
    ["2026-01-17", 1150],
    ["2026-01-31", 2300],
    ["2026-03-20", 1725],
    ["2026-03-27", 2300],
    ["2026-05-29", 1150],
    ["2026-06-05", 2300],
    ["2026-06-26", 1150],
    ["2026-07-10", 2300],
    ["2026-10-02", 1840],
    ["2026-10-09", 2300],
  ].map(([day, price]) => ({ day: day as string, price: price as number }));
  assert.equal(Math.round(timeWeightedAverage(points, "2026-10-09", 365)!), 2113);
});

test("no history", () => {
  assert.equal(timeWeightedAverage([], "2026-01-10"), null);
});

test("formats yen", () => {
  assert.equal(formatPrice(3465, "JPY"), "¥3,465");
  assert.equal(formatPrice(1999, "USD"), "19.99 USD");
});
