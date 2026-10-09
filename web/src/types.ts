export type Rarity = "legendary" | "epic" | "rare" | "uncommon" | "common";

export interface Player {
  id: string;
  steam_id: string | null;
  display_name: string;
  avatar_url: string | null;
  show_playtime: boolean;
  show_wishlist: boolean;
}

export interface Game {
  id: number;
  name: string;
  platform: string;
  steam_appid: number | null;
  header_image_url: string | null;
  lowest_price: number | null;
  lowest_price_currency: string | null;
  lowest_price_at: string | null;
}

export interface PlayerGame {
  game_id: number;
  source: string;
  playtime_minutes: number | null; // null when the player hides playtime
  last_played_at: string | null;
  achievements_total: number | null; // null: the game has no achievements
  achievements_unlocked: number | null;
  started_on: string | null; // YYYY-MM-DD, typed in the admin
}

export interface Activity {
  activity_date: string; // YYYY-MM-DD (JST)
  minutes_played: number | null;
  achievements_unlocked: number;
}

export interface Badge {
  game_id: number;
  game_name: string;
  api_name: string;
  display_name: string;
  description: string | null;
  icon_url: string | null;
  global_percent: number | null;
  rarity: Rarity | null;
  unlocked_at: string | null;
}

export interface AchievementDef {
  api_name: string;
  display_name: string;
  description: string | null;
  icon_url: string | null;
  icon_gray_url: string | null;
  hidden: boolean;
  global_percent: number | null;
}

export interface WishlistItem {
  game_id: number;
  added_at: string | null;
  priority: number | null;
}

export interface PriceRow {
  game_id: number;
  recorded_on: string; // YYYY-MM-DD (JST)
  price: number;
  regular_price: number;
  discount_pct: number;
  currency: string;
  sale_ends_at: string | null;
}

export interface GardenData {
  games: Map<number, Game>;
  playerGames: PlayerGame[];
  activity: Activity[];
  unlocked: Badge[]; // every unlocked achievement, rarest first
  wishlist: WishlistItem[];
  prices: Map<number, PriceRow[]>; // per game, oldest first
}
