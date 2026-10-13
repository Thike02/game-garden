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
      {player.avatar_url && (
        <span className={`avatar-wrap${player.avatar_frame_url ? " framed" : ""}`}>
          <img className="avatar" src={player.avatar_url} alt="" width={72} height={72} />
          {player.avatar_frame_url && (
            // Same as Steam: the frame is drawn over the avatar, a bit larger than it.
            <picture>
              {player.avatar_frame_static_url && (
                <source media="(prefers-reduced-motion: reduce)" srcSet={player.avatar_frame_static_url} />
              )}
              <img className="avatar-frame" src={player.avatar_frame_url} alt="" />
            </picture>
          )}
        </span>
      )}
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
