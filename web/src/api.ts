import { createClient } from "@supabase/supabase-js";
import type {
  Activity,
  Badge,
  Game,
  GardenData,
  Player,
  PlayerGame,
  PriceRow,
  WishlistItem,
} from "./types.ts";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const configured = Boolean(url && anonKey);

// The anon key only reads what RLS allows (public players, public sections).
const supabase = configured ? createClient(url!, anonKey!, { auth: { persistSession: false } }) : null;

const PAGE_SIZE = 1000; // PostgREST's default max rows per request
const BADGE_RARITIES = ["legendary", "epic", "rare"];

type Page<T> = PromiseLike<{ data: T[] | null; error: { message: string } | null }>;

async function fetchAll<T>(query: (from: number, to: number) => Page<T>): Promise<T[]> {
  const rows: T[] = [];
  for (let from = 0; ; from += PAGE_SIZE) {
    const { data, error } = await query(from, from + PAGE_SIZE - 1);
    if (error) throw new Error(error.message);
    rows.push(...(data ?? []));
    if (!data || data.length < PAGE_SIZE) return rows;
  }
}

function client() {
  if (!supabase) throw new Error("VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set");
  return supabase;
}

export async function loadPlayers(): Promise<Player[]> {
  const { data, error } = await client()
    .from("players")
    .select("id, steam_id, display_name, avatar_url, show_playtime, show_wishlist")
    .order("created_at");
  if (error) throw new Error(error.message);
  return data ?? [];
}

export async function loadGarden(player: Player): Promise<GardenData> {
  const db = client();
  const [games, playerGames, activity, badges, wishlist] = await Promise.all([
    fetchAll<Game>((from, to) =>
      db
        .from("games")
        .select("id, name, platform, steam_appid, header_image_url, lowest_price, lowest_price_currency, lowest_price_at")
        .order("id")
        .range(from, to),
    ),
    fetchAll<PlayerGame>((from, to) =>
      db
        .from("player_games")
        .select("game_id, source, playtime_minutes, last_played_at, achievements_total, achievements_unlocked")
        .eq("player_id", player.id)
        .order("game_id")
        .range(from, to),
    ),
    fetchAll<Activity>((from, to) =>
      db
        .from("player_activity")
        .select("activity_date, minutes_played, achievements_unlocked")
        .eq("player_id", player.id)
        .order("activity_date")
        .range(from, to),
    ),
    fetchAll<Badge>((from, to) =>
      db
        .from("player_achievement_badges")
        .select("game_id, game_name, api_name, display_name, description, icon_url, global_percent, rarity, unlocked_at")
        .eq("player_id", player.id)
        .in("rarity", BADGE_RARITIES)
        .order("global_percent")
        .range(from, to),
    ),
    player.show_wishlist
      ? fetchAll<WishlistItem>((from, to) =>
          db
            .from("wishlist_items")
            .select("game_id, added_at, priority")
            .eq("player_id", player.id)
            .is("removed_at", null)
            .order("game_id")
            .range(from, to),
        )
      : Promise.resolve([]),
  ]);

  const wishlistIds = wishlist.map((w) => w.game_id);
  const priceRows = wishlistIds.length
    ? await fetchAll<PriceRow>((from, to) =>
        db
          .from("price_history")
          .select("game_id, recorded_on, price, regular_price, discount_pct, currency, sale_ends_at")
          .eq("shop", "steam")
          .in("game_id", wishlistIds)
          .order("game_id")
          .order("recorded_on")
          .range(from, to),
      )
    : [];

  const prices = new Map<number, PriceRow[]>();
  for (const row of priceRows) {
    const list = prices.get(row.game_id) ?? [];
    list.push(row);
    prices.set(row.game_id, list);
  }

  return {
    games: new Map(games.map((g) => [g.id, g])),
    playerGames,
    activity,
    badges,
    wishlist,
    prices,
  };
}
