import { useMemo, useState } from "react";
import { formatJst } from "../dates.ts";
import type { Game, PlayerGame } from "../types.ts";
import { GameImage } from "./GameImage.tsx";

type SortKey = "progress" | "recent" | "playtime" | "name";

interface Props {
  games: Map<number, Game>;
  playerGames: PlayerGame[];
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

export function GameList({ games, playerGames, showPlaytime }: Props) {
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
      list.push({ game, owned, progress });
    }
    return list.sort(compare(sort));
  }, [games, playerGames, sort, onlyAchievements]);

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
      <ul className="games">
        {rows.map(({ game, owned, progress }) => (
          <li key={game.id} className="game">
            <GameImage src={game.header_image_url} width={184} height={69} label={game.platform} />
            <div className="game-body">
              <a
                className="game-name"
                href={game.steam_appid ? `https://store.steampowered.com/app/${game.steam_appid}/` : undefined}
                target="_blank"
                rel="noreferrer"
              >
                {game.name}
              </a>
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
              {showPlaytime && owned.playtime_minutes !== null && (
                <span className="muted small">
                  {(owned.playtime_minutes / 60).toFixed(1)} 時間
                  {owned.last_played_at &&
                    ` ・ 最後に遊んだ日 ${formatJst(owned.last_played_at, { year: "numeric", month: "numeric", day: "numeric" })}`}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
