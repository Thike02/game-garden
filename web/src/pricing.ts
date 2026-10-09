import { addDays, daysBetween } from "./dates.ts";

export interface PricePoint {
  day: string; // YYYY-MM-DD
  price: number;
}

/**
 * Average daily price over the last `days` days up to and including `today`.
 * Same rule as the collector (game_garden.pricing): each price is carried forward
 * until the next change, so sparse ITAD history doesn't over-count sale days.
 */
export function timeWeightedAverage(points: PricePoint[], today: string, days = 365): number | null {
  const windowStart = addDays(today, -(days - 1));
  const inEffect = points.filter((p) => p.day <= windowStart);
  const later = points.filter((p) => p.day > windowStart && p.day <= today);
  let segments: PricePoint[];
  if (inEffect.length) segments = [{ day: windowStart, price: inEffect[inEffect.length - 1].price }, ...later];
  else if (later.length) segments = later;
  else return null;

  const end = addDays(today, 1);
  let total = 0;
  segments.forEach((s, i) => {
    const next = i + 1 < segments.length ? segments[i + 1].day : end;
    total += s.price * daysBetween(s.day, next);
  });
  return total / daysBetween(segments[0].day, end);
}

export function formatPrice(amount: number, currency: string): string {
  if (currency === "JPY") return `¥${amount.toLocaleString("ja-JP")}`;
  return `${(amount / 100).toFixed(2)} ${currency}`;
}
