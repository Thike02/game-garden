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
  hidden?: boolean;
}

/** Hover card body for one achievement. */
export function AchievementCard({ achievement: a }: { achievement: AchievementLike }) {
  return (
    <span className="achievement-card">
      {a.icon_url && <img src={a.icon_url} alt="" width={48} height={48} />}
      <span className="achievement-card-body">
        <strong>{a.display_name}</strong>
        {a.game_name && <span className="muted small">{a.game_name}</span>}
        {/* Steam's API omits descriptions of hidden achievements; others may simply have none. */}
        {a.description ? (
          <span className="small">{a.description}</span>
        ) : (
          a.hidden && <span className="small muted">隠し実績</span>
        )}
        {a.global_percent !== null && (
          <span className={`small rarity-text ${a.rarity ?? ""}`}>全体の {a.global_percent.toFixed(1)}% が解除</span>
        )}
        {a.unlocked_at && (
          <span className="small muted">
            {formatJst(a.unlocked_at, { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })} に解除
          </span>
        )}
      </span>
    </span>
  );
}
