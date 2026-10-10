import { useMemo, useState } from "react";
import { formatJst } from "../dates.ts";
import type { Badge, Game, PlayerGame, Tag } from "../types.ts";
import { GameAchievements } from "./GameAchievements.tsx";
import { HoverCard } from "./HoverCard.tsx";
import { GameImage } from "./GameImage.tsx";

type SortKey = "progress" | "recent" | "playtime" | "name";

interface Props {
  games: Map<number, Game>;
  playerGames: PlayerGame[];
  unlocked: Badge[];
  tags: Tag[];
  gameTags: Map<number, number[]>;
  showPlaytime: boolean;
}

interface Row {
  game: Game;
  owned: PlayerGame;
  progress: number | null; // 0..1, null when the game has no achievements
}

function compare(sort: SortKey) {
  return (a: Row, b: Row): number => {
    switch (sort) {
      case "progress":
        return (b.progress ?? -1) - (a.progress ?? -1) || a.game.name.localeCompare(b.game.name);
      case "recent":
        return (b.owned.last_played_at ?? "").localeCompare(a.owned.last_played_at ?? "");
      case "playtime":
        return (b.owned.playtime_minutes ?? 0) - (a.owned.playtime_minutes ?? 0);
      case "name":
        return a.game.name.localeCompare(b.game.name, "ja");
    }
  };
}

function PlayLine({ owned }: { owned: PlayerGame }) {
  const parts: string[] = [];
  // Hand-entered games often have no playtime; don't show "0.0 時間" for them.
  if (owned.playtime_minutes !== null && (owned.source === "steam" || owned.playtime_minutes > 0)) {
    parts.push(`${(owned.playtime_minutes / 60).toFixed(1)} 時間`);
  }
  if (owned.last_played_at) {
    parts.push(`最後に遊んだ日 ${formatJst(owned.last_played_at, { year: "numeric", month: "numeric", day: "numeric" })}`);
  }
  return parts.length ? <span className="muted small">{parts.join(" ・ ")}</span> : null;
}

function Summary({ owned, game }: { owned: PlayerGame; game: Game }) {
  const total = owned.achievements_total ?? 0;
  const done = owned.achievements_unlocked ?? 0;
  return (
    <span className="day-card">
      <strong>{game.name}</strong>
      <span className="small">
        {total === 0
          ? "実績はありません"
          : done === total
            ? `${done}/${total} ・ コンプリート！✨`
            : `${done}/${total} ・ あと ${total - done} 個`}
      </span>
      {owned.source === "manual" && <span className="muted small">{game.platform}・手で記録</span>}
      {total > 0 && owned.source !== "manual" && <span className="muted small">押すと実績の一覧が開きます</span>}
    </span>
  );
}

export function GameList({ games, playerGames, unlocked, tags, gameTags, showPlaytime }: Props) {
  const [open, setOpen] = useState<number | null>(null);
  const [tagFilter, setTagFilter] = useState<number | null>(null);
  const tagById = useMemo(() => new Map(tags.map((t) => [t.id, t])), [tags]);
  const unlockedByGame = useMemo(() => {
    const map = new Map<number, Badge[]>();
    for (const a of unlocked) map.set(a.game_id, [...(map.get(a.game_id) ?? []), a]);
    return map;
  }, [unlocked]);
  const [sort, setSort] = useState<SortKey>(showPlaytime ? "recent" : "progress");
  const [onlyAchievements, setOnlyAchievements] = useState(false);

  const rows = useMemo(() => {
    const list: Row[] = [];
    for (const owned of playerGames) {
      const game = games.get(owned.game_id);
      if (!game) continue;
      const total = owned.achievements_total ?? 0;
      const progress = total > 0 ? (owned.achievements_unlocked ?? 0) / total : null;
      if (onlyAchievements && progress === null) continue;
      if (tagFilter !== null && !(gameTags.get(game.id) ?? []).includes(tagFilter)) continue;
      list.push({ game, owned, progress });
    }
    return list.sort(compare(sort));
  }, [games, playerGames, sort, onlyAchievements, tagFilter, gameTags]);

  return (
    <section className="panel">
      <div className="section-head">
        <h2>🎮 ゲーム</h2>
        <div className="controls small">
          <label>
            <input type="checkbox" checked={onlyAchievements} onChange={(e) => setOnlyAchievements(e.target.checked)} />
            実績があるものだけ
          </label>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="並び替え">
            {showPlaytime && <option value="recent">最近遊んだ順</option>}
            <option value="progress">達成率順</option>
            {showPlaytime && <option value="playtime">プレイ時間順</option>}
            <option value="name">名前順</option>
          </select>
        </div>
      </div>
      {tags.length > 0 && (
        <div className="tag-filter" role="group" aria-label="タグで絞り込み">
          {tags.map((t) => (
            <button
              key={t.id}
              className={`tag-chip tag-${t.color}`}
              aria-pressed={tagFilter === t.id}
              onClick={() => setTagFilter(tagFilter === t.id ? null : t.id)}
            >
              {t.name}
            </button>
          ))}
        </div>
      )}
      <ul className="games">
        {rows.map(({ game, owned, progress }) => {
          const expanded = open === game.id;
          // Hand-entered games only have counts, no per-achievement data.
          const expandable = progress !== null && owned.source !== "manual";
          const toggle = () => expandable && setOpen(expanded ? null : game.id);
          return (
          <li key={game.id} className={`game-item${expanded ? " expanded" : ""}`}>
            <HoverCard className="game-hover" tapToOpen={false} width={280} content={() => <Summary owned={owned} game={game} />}>
            <div
              className={`game${expandable ? " clickable" : ""}`}
              role={expandable ? "button" : undefined}
              aria-expanded={expandable ? expanded : undefined}
              onClick={toggle}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), toggle())}
            >
            <GameImage src={game.header_image_url} width={184} height={69} label={game.platform} />
            <div className="game-body">
              <a
                className="game-name"
                href={game.steam_appid ? `https://store.steampowered.com/app/${game.steam_appid}/` : undefined}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                {game.name}
              </a>
              {(owned.source === "manual" || gameTags.has(game.id)) && (
                <span className="chips">
                  {owned.source === "manual" && <span className="platform-chip small">{game.platform}</span>}
                  {(gameTags.get(game.id) ?? [])
                    .map((id) => tagById.get(id))
                    .filter((t): t is Tag => t !== undefined)
                    .map((t) => (
                      <span key={t.id} className={`tag-chip small tag-${t.color}`}>
                        {t.name}
                      </span>
                    ))}
                </span>
              )}
              {progress === null ? (
                <span className="muted small">実績なし</span>
              ) : (
                <div className="progress-row small">
                  <div className="progress" aria-label={`達成率 ${Math.round(progress * 100)}%`}>
                    <div className={`progress-fill${progress === 1 ? " complete" : ""}`} style={{ width: `${progress * 100}%` }} />
                  </div>
                  <span>
                    {owned.achievements_unlocked}/{owned.achievements_total}
                    {progress === 1 && " ✨"}
                  </span>
                </div>
              )}
              {/* Kept in the data for Steam games too (e.g. a game moved to Steam), but only shown for the others. */}
              {owned.started_on && owned.source !== "steam" && (
                <span className="muted small">{owned.started_on.replaceAll("-", "/")} から遊んでいます</span>
              )}
              {showPlaytime && (
                <PlayLine owned={owned} />
              )}
            </div>
            </div>
            </HoverCard>
            {expanded && <GameAchievements gameId={game.id} unlocked={unlockedByGame.get(game.id) ?? []} />}
          </li>
          );
        })}
      </ul>
    </section>
  );
}
