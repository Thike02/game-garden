import { useEffect, useMemo, useState } from "react";
import { loadGameAchievements } from "../api.ts";
import { formatJst } from "../dates.ts";
import type { AchievementDef, Badge } from "../types.ts";
import { AchievementCard } from "./AchievementCard.tsx";
import { HoverCard } from "./HoverCard.tsx";

type Sort = "unlocked" | "rarity";

interface Props {
  gameId: number;
  unlocked: Badge[]; // this game's unlocked achievements
}

interface Row {
  def: AchievementDef;
  unlockedAt: string | null;
  isUnlocked: boolean;
}

// Same thresholds as public.achievement_rarity() in supabase/migrations/0002; keep them in sync.
function rarityOf(percent: number | null): string {
  if (percent === null) return "";
  if (percent < 1) return "legendary";
  if (percent < 5) return "epic";
  if (percent < 10) return "rare";
  return "";
}

export function GameAchievements({ gameId, unlocked }: Props) {
  const [defs, setDefs] = useState<AchievementDef[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<Sort>("unlocked");
  const [lockedOnly, setLockedOnly] = useState(false);

  useEffect(() => {
    loadGameAchievements(gameId)
      .then(setDefs)
      .catch((e: Error) => setError(e.message));
  }, [gameId]);

  const rows = useMemo(() => {
    if (!defs) return [];
    const unlockedAt = new Map(unlocked.map((a) => [a.api_name, a.unlocked_at]));
    const list: Row[] = defs.map((def) => ({
      def,
      isUnlocked: unlockedAt.has(def.api_name),
      unlockedAt: unlockedAt.get(def.api_name) ?? null,
    }));
    const rarity = (r: Row) => r.def.global_percent ?? 101;
    return list
      .filter((r) => !lockedOnly || !r.isUnlocked)
      .sort((a, b) =>
        sort === "rarity"
          ? rarity(a) - rarity(b)
          : // Unlocked first, newest first; then locked, most common first (easiest next)
            Number(b.isUnlocked) - Number(a.isUnlocked) ||
            (b.unlockedAt ?? "").localeCompare(a.unlockedAt ?? "") ||
            rarity(b) - rarity(a),
      );
  }, [defs, unlocked, sort, lockedOnly]);

  if (error) return <p className="error small">実績を読み込めませんでした：{error}</p>;
  if (!defs) return <p className="muted small">実績を読み込み中…</p>;

  return (
    <div className="game-achievements">
      <div className="controls small">
        <div className="toggle" role="group" aria-label="並び替え">
          <button aria-pressed={sort === "unlocked"} onClick={() => setSort("unlocked")}>
            解除した順
          </button>
          <button aria-pressed={sort === "rarity"} onClick={() => setSort("rarity")}>
            レアな順
          </button>
        </div>
        <label>
          <input type="checkbox" checked={lockedOnly} onChange={(e) => setLockedOnly(e.target.checked)} />
          未解除だけ
        </label>
      </div>
      {rows.length === 0 ? (
        <p className="muted small">未解除の実績はありません。コンプリート！✨</p>
      ) : (
        <ul className="achievement-list">
          {rows.map(({ def, isUnlocked, unlockedAt }) => {
            // Locked hidden achievements stay secret, like on Steam.
            const secret = def.hidden && !isUnlocked;
            const shown = {
              display_name: secret ? "隠し実績" : def.display_name,
              description: secret ? "解除すると内容がわかります。" : def.description,
              icon_url: isUnlocked ? def.icon_url : def.icon_gray_url,
              global_percent: def.global_percent,
              unlocked_at: unlockedAt,
            };
            const rarity = rarityOf(def.global_percent);
            return (
              <li key={def.api_name}>
                <HoverCard
                  className={`achievement-row${isUnlocked ? "" : " locked"} ${rarity}`}
                  content={() => <AchievementCard achievement={{ ...shown, rarity: rarity as Badge["rarity"] }} />}
                >
                  {shown.icon_url ? <img src={shown.icon_url} alt="" width={40} height={40} loading="lazy" /> : <span className="day-icon-blank" />}
                  <span className="achievement-row-body">
                    <span className="achievement-name">{shown.display_name}</span>
                    <span className="muted small">{shown.description}</span>
                  </span>
                  <span className="achievement-meta small">
                    <span className={`rarity-text ${rarity}`}>{def.global_percent?.toFixed(1)}%</span>
                    <span className="muted">
                      {unlockedAt ? formatJst(unlockedAt, { year: "numeric", month: "numeric", day: "numeric" }) : isUnlocked ? "解除" : "未解除"}
                    </span>
                  </span>
                </HoverCard>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
