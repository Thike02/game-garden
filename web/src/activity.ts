import { addDays, weekday } from "./dates.ts";
import type { Activity } from "./types.ts";

export type ActivityMode = "achievements" | "playtime";

export interface Cell {
  day: string;
  value: number;
  level: 0 | 1 | 2 | 3 | 4;
  inRange: boolean; // false for padding cells after today
}

export function valueOf(a: Activity, mode: ActivityMode): number {
  return mode === "achievements" ? a.achievements_unlocked : (a.minutes_played ?? 0);
}

/** Level 1-4 by quartile of the non-zero values, like GitHub's contribution graph. */
export function levelFor(value: number, sortedNonZero: number[]): Cell["level"] {
  if (value <= 0 || sortedNonZero.length === 0) return 0;
  const rank = sortedNonZero.filter((v) => v < value).length / sortedNonZero.length;
  return rank < 0.25 ? 1 : rank < 0.5 ? 2 : rank < 0.75 ? 3 : 4;
}

/**
 * Columns of 7 days (Sunday first), ending with the week that contains `today`.
 * Covers `weeks` weeks.
 */
export function buildWeeks(activity: Activity[], today: string, mode: ActivityMode, weeks = 53): Cell[][] {
  const byDay = new Map(activity.map((a) => [a.activity_date, valueOf(a, mode)]));
  const lastSaturday = addDays(today, 6 - weekday(today));
  const firstSunday = addDays(lastSaturday, -(weeks * 7 - 1));

  const values: number[] = [];
  for (let d = firstSunday; d <= today; d = addDays(d, 1)) {
    const v = byDay.get(d) ?? 0;
    if (v > 0) values.push(v);
  }
  values.sort((a, b) => a - b);

  const columns: Cell[][] = [];
  for (let w = 0; w < weeks; w++) {
    const column: Cell[] = [];
    for (let i = 0; i < 7; i++) {
      const day = addDays(firstSunday, w * 7 + i);
      const inRange = day <= today;
      const value = inRange ? (byDay.get(day) ?? 0) : 0;
      column.push({ day, value, level: inRange ? levelFor(value, values) : 0, inRange });
    }
    columns.push(column);
  }
  return columns;
}
