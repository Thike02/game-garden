import { useMemo, useState } from "react";
import { type ActivityMode, buildWeeks } from "../activity.ts";
import { todayJst } from "../dates.ts";
import type { Activity } from "../types.ts";

interface Props {
  activity: Activity[];
  showPlaytime: boolean;
}

const WEEKDAY_LABELS = ["", "月", "", "水", "", "金", ""];

function describe(value: number, mode: ActivityMode): string {
  if (mode === "achievements") return `実績 ${value} 個`;
  return value >= 60 ? `${Math.floor(value / 60)} 時間 ${value % 60} 分` : `${value} 分`;
}

export function Garden({ activity, showPlaytime }: Props) {
  const [mode, setMode] = useState<ActivityMode>("achievements");
  const today = todayJst();
  const weeks = useMemo(() => buildWeeks(activity, today, mode), [activity, today, mode]);

  const total = weeks.flat().reduce((sum, c) => sum + c.value, 0);
  const activeDays = weeks.flat().filter((c) => c.value > 0).length;
  const summary =
    mode === "achievements"
      ? `この1年で ${total.toLocaleString("ja-JP")} 個の実績を解除（${activeDays} 日）`
      : `この1年で ${Math.round(total / 60).toLocaleString("ja-JP")} 時間プレイ（${activeDays} 日）`;

  // Month label over the first column whose Sunday starts a new month.
  const monthLabels = weeks.map((column, i) => {
    const month = column[0].day.slice(5, 7);
    const prev = i > 0 ? weeks[i - 1][0].day.slice(5, 7) : null;
    return month !== prev ? `${Number(month)}月` : "";
  });

  return (
    <section className="panel">
      <div className="section-head">
        <h2>🌱 庭</h2>
        {showPlaytime && (
          <div className="toggle" role="group" aria-label="草の種類">
            <button aria-pressed={mode === "achievements"} onClick={() => setMode("achievements")}>
              実績
            </button>
            <button aria-pressed={mode === "playtime"} onClick={() => setMode("playtime")}>
              プレイ時間
            </button>
          </div>
        )}
      </div>
      <p className="muted">{summary}</p>
      {mode === "playtime" && (
        <p className="muted small">プレイ時間は毎日の記録の差から数えるので、記録を始めた日より前の分はありません。</p>
      )}
      <div className="garden-scroll">
        <div className="garden">
          <div className="garden-months">
            {monthLabels.map((label, i) => (
              <span key={i}>{label}</span>
            ))}
          </div>
          <div className="garden-weekdays">
            {WEEKDAY_LABELS.map((label, i) => (
              <span key={i}>{label}</span>
            ))}
          </div>
          <div className="garden-grid">
            {weeks.map((column, w) => (
              <div className="garden-week" key={w}>
                {column.map((cell) => (
                  <span
                    key={cell.day}
                    className={`cell level-${cell.level}${cell.inRange ? "" : " out"}`}
                    title={cell.inRange ? `${cell.day}：${describe(cell.value, mode)}` : undefined}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="legend muted small">
        少ない
        {[0, 1, 2, 3, 4].map((level) => (
          <span key={level} className={`cell level-${level}`} />
        ))}
        多い
      </div>
    </section>
  );
}
