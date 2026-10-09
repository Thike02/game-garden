import type { GardenData, Player } from "../types.ts";

interface Props {
  player: Player;
  data: GardenData;
}

export function Profile({ player, data }: Props) {
  const withAchievements = data.playerGames.filter((g) => g.achievements_total);
  const unlocked = withAchievements.reduce((sum, g) => sum + (g.achievements_unlocked ?? 0), 0);
  const perfect = withAchievements.filter((g) => g.achievements_unlocked === g.achievements_total).length;
  const minutes = player.show_playtime
    ? data.playerGames.reduce((sum, g) => sum + (g.playtime_minutes ?? 0), 0)
    : null;

  const stats: [string, string][] = [
    ["持っているゲーム", `${data.playerGames.length}`],
    ["解除した実績", unlocked.toLocaleString("ja-JP")],
    ["コンプリート", `${perfect}`],
  ];
  if (minutes !== null) stats.push(["合計プレイ時間", `${Math.round(minutes / 60).toLocaleString("ja-JP")} 時間`]);

  return (
    <section className="panel profile">
      {player.avatar_url && <img className="avatar" src={player.avatar_url} alt="" width={72} height={72} />}
      <div className="profile-body">
        <h1>{player.display_name} の庭</h1>
        <dl className="stats">
          {stats.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
