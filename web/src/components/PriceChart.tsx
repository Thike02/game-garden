import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { addDays } from "../dates.ts";
import { formatPrice } from "../pricing.ts";
import { useIsPhone } from "../useIsPhone.ts";
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
  const isPhone = useIsPhone();
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

  // Zoom the price axis to where the prices move instead of starting at ¥0.
  const values = [...data.map((d) => d.price), ...(lowest !== null ? [lowest] : []), ...(average !== null ? [average] : [])];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = Math.max((high - low) * 0.15, high * 0.05);
  const step = high >= 1000 ? 100 : 10; // round the ends to tidy numbers
  const domain: [number, number] = [Math.max(0, Math.floor((low - pad) / step) * step), Math.ceil((high + pad) / step) * step];

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
      {/* Legend instead of labels on the lines, which overlapped the price line on phones */}
      <div className="chart-legend small">
        <span className="legend-price">━ 価格</span>
        {lowest !== null && <span className="legend-low">- - 最安値 {formatPrice(lowest, currency)}</span>}
        {average !== null && <span className="legend-avg">··· 1年の平均 {formatPrice(Math.round(average), currency)}</span>}
      </div>
      <ResponsiveContainer width="100%" height={isPhone ? 200 : 220}>
        <LineChart data={data} margin={{ top: 8, right: isPhone ? 8 : 16, bottom: 0, left: isPhone ? 0 : 8 }}>
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
            fontSize={isPhone ? 11 : 12}
            width={isPhone ? 52 : 64}
            domain={domain}
            allowDataOverflow
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
            <ReferenceLine y={lowest} stroke="var(--legendary)" strokeDasharray="4 4" />
          )}
          {average !== null && (
            <ReferenceLine y={average} stroke="var(--muted)" strokeDasharray="2 4" />
          )}
          <Line type="stepAfter" dataKey="price" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
