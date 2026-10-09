import { useState } from "react";
import { formatJst } from "../dates.ts";
import type { Badge, Rarity } from "../types.ts";
import { HoverCard } from "./HoverCard.tsx";
import { AchievementCard } from "./AchievementCard.tsx";

const RARITY_LABEL: Record<Rarity, string> = {
  legendary: "Legendary",
  epic: "Epic",
  rare: "Rare",
  uncommon: "Uncommon",
  common: "Common",
};
const INITIAL = 24;

export function Badges({ badges }: { badges: Badge[] }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? badges : badges.slice(0, INITIAL);

  const counts = badges.reduce<Partial<Record<Rarity, number>>>((acc, b) => {
    if (b.rarity) acc[b.rarity] = (acc[b.rarity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="panel">
      <div className="section-head">
        <h2>🏆 レア実績</h2>
        <div className="rarity-counts small">
          {(["legendary", "epic", "rare"] as const).map((r) => (
            <span key={r} className={`rarity-chip ${r}`}>
              {RARITY_LABEL[r]} {counts[r] ?? 0}
            </span>
          ))}
        </div>
      </div>
      {badges.length === 0 ? (
        <p className="muted">まだレア実績はありません。</p>
      ) : (
        <ul className="badges">
          {shown.map((b) => (
            <li key={`${b.game_id}:${b.api_name}`}>
              <HoverCard className={`badge ${b.rarity ?? ""}`} content={() => <AchievementCard achievement={b} />}>
                {b.icon_url ? <img src={b.icon_url} alt="" width={64} height={64} loading="lazy" /> : <span className="badge-blank" />}
                <span className="badge-body">
                  <strong>{b.display_name}</strong>
                  <span className="muted small">{b.game_name}</span>
                  <span className="small">
                    <span className={`rarity-text ${b.rarity ?? ""}`}>{b.global_percent?.toFixed(1)}%</span>
                    {b.unlocked_at && (
                      <span className="muted"> ・ {formatJst(b.unlocked_at, { year: "numeric", month: "numeric", day: "numeric" })}</span>
                    )}
                  </span>
                </span>
              </HoverCard>
            </li>
          ))}
        </ul>
      )}
      {badges.length > INITIAL && (
        <button className="link-button" onClick={() => setExpanded(!expanded)}>
          {expanded ? "たたむ" : `ぜんぶ見る（${badges.length} 個）`}
        </button>
      )}
    </section>
  );
}
