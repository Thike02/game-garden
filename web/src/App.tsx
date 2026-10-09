import { useEffect, useState } from "react";
import { configured, loadGarden, loadPlayers } from "./api.ts";
import { Badges } from "./components/Badges.tsx";
import { GameList } from "./components/GameList.tsx";
import { Garden } from "./components/Garden.tsx";
import { Profile } from "./components/Profile.tsx";
import { ThemeToggle } from "./components/ThemeToggle.tsx";
import { Wishlist } from "./components/Wishlist.tsx";
import type { GardenData, Player } from "./types.ts";

const BADGE_RARITIES = new Set(["legendary", "epic", "rare"]);

// ?player=<SteamID64> picks a player; otherwise the first public one is shown.
function initialSteamId(): string | null {
  return new URLSearchParams(window.location.search).get("player");
}

export function App() {
  const [players, setPlayers] = useState<Player[] | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [data, setData] = useState<GardenData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!configured) return;
    loadPlayers()
      .then((list) => {
        setPlayers(list);
        const wanted = initialSteamId();
        setPlayer(list.find((p) => p.steam_id === wanted) ?? list[0] ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!player) return;
    setData(null);
    loadGarden(player)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [player]);

  const choose = (id: string) => {
    const next = players?.find((p) => p.id === id) ?? null;
    setPlayer(next);
    const params = new URLSearchParams(window.location.search);
    if (next?.steam_id) params.set("player", next.steam_id);
    window.history.replaceState(null, "", `?${params}`);
  };

  let body;
  if (!configured) body = <p className="panel">VITE_SUPABASE_URL と VITE_SUPABASE_ANON_KEY が設定されていません。</p>;
  else if (error) body = <p className="panel error">読み込みに失敗しました：{error}</p>;
  else if (players && players.length === 0) body = <p className="panel">公開されているプレイヤーがいません。</p>;
  else if (!player || !data) body = <p className="panel muted">読み込み中…</p>;
  else
    body = (
      <>
        <Profile player={player} data={data} />
        <Garden activity={data.activity} unlocked={data.unlocked} showPlaytime={player.show_playtime} />
        <Badges badges={data.unlocked.filter((a) => a.rarity && BADGE_RARITIES.has(a.rarity))} />
        <GameList
          games={data.games}
          playerGames={data.playerGames}
          unlocked={data.unlocked}
          showPlaytime={player.show_playtime}
        />
        {player.show_wishlist && <Wishlist games={data.games} wishlist={data.wishlist} prices={data.prices} />}
      </>
    );

  return (
    <>
      <header className="topbar">
        <span className="brand">🌱 Game Garden</span>
        <div className="topbar-actions">
          {players && players.length > 1 && (
            <select value={player?.id ?? ""} onChange={(e) => choose(e.target.value)} aria-label="プレイヤー">
              {players.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main>{body}</main>
      <footer className="muted small">
        データは毎朝4時ごろ更新されます。Steam の情報は Valve Corporation に帰属します。価格の履歴は{" "}
        <a href="https://isthereanydeal.com/" target="_blank" rel="noreferrer">
          IsThereAnyDeal
        </a>{" "}
        から取得しています。
      </footer>
    </>
  );
}
