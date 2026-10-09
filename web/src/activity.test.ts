import assert from "node:assert/strict";
import { test } from "node:test";
import { buildWeeks, levelFor } from "./activity.ts";

test("levels split non-zero values into quartiles", () => {
  const values = [1, 2, 3, 4, 5, 6, 7, 8];
  assert.equal(levelFor(0, values), 0);
  assert.equal(levelFor(1, values), 1);
  assert.equal(levelFor(3, values), 2);
  assert.equal(levelFor(5, values), 3);
  assert.equal(levelFor(8, values), 4);
});

test("weeks start on Sunday and end with the week of today", () => {
  // 2026-10-09 is a Friday
  const weeks = buildWeeks([], "2026-10-09", "achievements", 2);
  assert.equal(weeks.length, 2);
  assert.equal(weeks[0][0].day, "2026-09-27");
  assert.equal(weeks[1][6].day, "2026-10-10");
  assert.equal(weeks[1][5].inRange, true);
  assert.equal(weeks[1][6].inRange, false);
});

test("modes read the right column and hidden playtime counts as zero", () => {
  const activity = [
    { activity_date: "2026-10-08", minutes_played: 90, achievements_unlocked: 2 },
    { activity_date: "2026-10-09", minutes_played: null, achievements_unlocked: 1 },
  ];
  const achievements = buildWeeks(activity, "2026-10-09", "achievements", 1)[0];
  const playtime = buildWeeks(activity, "2026-10-09", "playtime", 1)[0];
  assert.deepEqual(achievements.slice(4, 6).map((c) => c.value), [2, 1]);
  assert.deepEqual(playtime.slice(4, 6).map((c) => c.value), [90, 0]);
});
