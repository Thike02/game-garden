import { formatJst } from "../dates.ts";
import type { Rarity } from "../types.ts";

export interface AchievementLike {
  display_name: string;
  description: string | null;
  icon_url: string | null;
  global_percent: number | null;
  rarity?: Rarity | null;
  game_name?: string;
  unlocked_at?: string | null;
}

/** Hover card body for one achievement. */
export function AchievementCard({ achievement: a }: { achievement: AchievementLike }) {
  return (
    <span className="achievement-card">
      {a.icon_url && <img src={a.icon_url} alt="" width={48} height={48} />}
      <span className="achievement-card-body">
        <strong>{a.display_name}</strong>
        {a.game_name && <span className="muted small">{a.game_name}</span>}
        <span className="small">{a.description || <span className="muted">（説明なし）</span>}</span>
        <span className="small">
          {a.global_percent !== null && (
            <span className={`rarity-text ${a.rarity ?? ""}`}>全体の {a.global_percent.toFixed(1)}% が解除</span>
          )}
          {a.unlocked_at && (
            <span className="muted">
              {" ・ "}
              {formatJst(a.unlocked_at, { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })} に解除
            </span>
          )}
        </span>
      </span>
    </span>
  );
}
