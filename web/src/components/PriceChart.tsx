import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { addDays } from "../dates.ts";
import { formatPrice } from "../pricing.ts";
import type { PriceRow } from "../types.ts";

interface Props {
  rows: PriceRow[]; // oldest first
  today: string;
  lowest: number | null;
  average: number | null;
}

type Range = "1y" | "all";

const toTime = (day: string) => Date.parse(`${day}T00:00:00Z`);

export function PriceChart({ rows, today, lowest, average }: Props) {
  const [range, setRange] = useState<Range>("1y");
  if (rows.length === 0) return <p className="muted small">価格の記録がまだありません。</p>;

  const currency = rows[rows.length - 1].currency;
  const start = range === "1y" ? addDays(today, -364) : rows[0].recorded_on;
  const before = rows.filter((r) => r.recorded_on <= start);
  const inRange = rows.filter((r) => r.recorded_on > start);
  // Start the line at the price in effect on the first day, and extend it to today.
  const points = [
    ...(before.length ? [{ ...before[before.length - 1], recorded_on: start }] : []),
    ...inRange,
  ];
  const last = points[points.length - 1];
  if (last && last.recorded_on < today) points.push({ ...last, recorded_on: today });
  const data = points.map((r) => ({ t: toTime(r.recorded_on), price: r.price, discount: r.discount_pct }));

  const ticks = (value: number) => {
    const d = new Date(value);
    return `${d.getUTCFullYear() % 100}/${d.getUTCMonth() + 1}`;
  };

  return (
    <div className="price-chart">
      <div className="toggle small" role="group" aria-label="期間">
        <button aria-pressed={range === "1y"} onClick={() => setRange("1y")}>
          1年
        </button>
        <button aria-pressed={range === "all"} onClick={() => setRange("all")}>
          全期間
        </button>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={ticks}
            stroke="var(--muted)"
            fontSize={12}
          />
          <YAxis
            stroke="var(--muted)"
            fontSize={12}
            width={64}
            domain={[0, "auto"]}
            tickFormatter={(v: number) => formatPrice(v, currency)}
          />
          <Tooltip
            contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", color: "var(--text)" }}
            labelFormatter={(value) => new Date(Number(value)).toISOString().slice(0, 10)}
            formatter={(value, _name, item) => {
              const discount = (item?.payload as { discount: number } | undefined)?.discount ?? 0;
              return [`${formatPrice(Number(value), currency)}${discount ? `（-${discount}%）` : ""}`, "価格"];
            }}
          />
          {lowest !== null && (
            <ReferenceLine y={lowest} stroke="var(--legendary)" strokeDasharray="4 4" label={{ value: "最安値", fill: "var(--legendary)", fontSize: 11, position: "insideBottomLeft" }} />
          )}
          {average !== null && (
            <ReferenceLine y={average} stroke="var(--muted)" strokeDasharray="2 4" label={{ value: "1年の平均", fill: "var(--muted)", fontSize: 11, position: "insideTopLeft" }} />
          )}
          <Line type="stepAfter" dataKey="price" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
