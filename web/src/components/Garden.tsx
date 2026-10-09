import { useMemo, useState } from "react";
import { type ActivityMode, buildWeeks } from "../activity.ts";
import { dayJst, todayJst } from "../dates.ts";
import type { Activity, Badge } from "../types.ts";
import { HoverCard } from "./HoverCard.tsx";

interface Props {
  activity: Activity[];
  unlocked: Badge[]; // rarest first
  showPlaytime: boolean;
}

const LIST_LIMIT = 8;

const WEEKDAY_LABELS = ["", "月", "", "水", "", "金", ""];

function describe(value: number, mode: ActivityMode): string {
  if (mode === "achievements") return `実績 ${value} 個`;
  return value >= 60 ? `${Math.floor(value / 60)} 時間 ${value % 60} 分` : `${value} 分`;
}

function DayCard({ day, value, mode, achievements }: { day: string; value: number; mode: ActivityMode; achievements: Badge[] }) {
  return (
    <span className="day-card">
      <strong>{day.replaceAll("-", "/")}</strong>
      <span className="small">{value > 0 ? describe(value, mode) : mode === "achievements" ? "解除した実績なし" : "プレイなし"}</span>
      {mode === "achievements" && achievements.length > 0 && (
        <span className="day-list">
          {achievements.slice(0, LIST_LIMIT).map((a) => (
            <span key={`${a.game_id}:${a.api_name}`} className="day-item small">
              {a.icon_url ? <img src={a.icon_url} alt="" width={24} height={24} /> : <span className="day-icon-blank" />}
              <span className="day-item-text">
                <span className={`rarity-dot ${a.rarity ?? ""}`} />
                {a.display_name}
                <span className="muted">（{a.game_name}）</span>
              </span>
              <span className={`rarity-text ${a.rarity ?? ""}`}>{a.global_percent?.toFixed(1)}%</span>
            </span>
          ))}
          {achievements.length > LIST_LIMIT && <span className="muted small">ほか {achievements.length - LIST_LIMIT} 個</span>}
        </span>
      )}
    </span>
  );
}

export function Garden({ activity, unlocked, showPlaytime }: Props) {
  const [mode, setMode] = useState<ActivityMode>("achievements");
  const today = todayJst();
  const weeks = useMemo(() => buildWeeks(activity, today, mode), [activity, today, mode]);
  const unlockedByDay = useMemo(() => {
    const map = new Map<string, Badge[]>();
    for (const a of unlocked) {
      if (!a.unlocked_at) continue;
      const day = dayJst(a.unlocked_at);
      map.set(day, [...(map.get(day) ?? []), a]);
    }
    return map;
  }, [unlocked]);

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
                {column.map((cell) =>
                  cell.inRange ? (
                    <HoverCard
                      key={cell.day}
                      className={`cell level-${cell.level}`}
                      width={340}
                      content={() => (
                        <DayCard day={cell.day} value={cell.value} mode={mode} achievements={unlockedByDay.get(cell.day) ?? []} />
                      )}
                    >
                      {null}
                    </HoverCard>
                  ) : (
                    <span key={cell.day} className="cell out" />
                  ),
                )}
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
