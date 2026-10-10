import { lazy, Suspense, useMemo, useState } from "react";
import { addDays, formatJst, todayJst } from "../dates.ts";
import { formatPrice, timeWeightedAverage } from "../pricing.ts";
import type { Game, PriceRow, WishlistItem } from "../types.ts";
import { GameImage } from "./GameImage.tsx";

// Recharts is most of the bundle; load it only when a chart is opened.
const PriceChart = lazy(() => import("./PriceChart.tsx").then((m) => ({ default: m.PriceChart })));

interface Props {
  games: Map<number, Game>;
  wishlist: WishlistItem[];
  prices: Map<number, PriceRow[]>;
}

interface Row {
  game: Game;
  history: PriceRow[];
  current: PriceRow | null; // latest daily price, null if unreleased / no longer sold
  average: number | null;
  isLow: boolean;
}

export function Wishlist({ games, wishlist, prices }: Props) {
  const [open, setOpen] = useState<number | null>(null);
  const today = todayJst();

  const rows = useMemo(() => {
    const list: Row[] = [];
    for (const item of wishlist) {
      const game = games.get(item.game_id);
      if (!game) continue;
      const history = prices.get(item.game_id) ?? [];
      const latest = history[history.length - 1];
      // The collector runs at 04:00 JST, so before that yesterday's price is still the latest.
      const current = latest && latest.recorded_on >= addDays(today, -1) ? latest : null;
      const average = timeWeightedAverage(
        history.map((r) => ({ day: r.recorded_on, price: r.price })),
        today,
      );
      const isLow = Boolean(current && current.discount_pct > 0 && game.lowest_price !== null && current.price <= game.lowest_price);
      list.push({ game, history, current, average, isLow });
    }
    // Sales first (lows on top), then the rest by name.
    return list.sort(
      (a, b) =>
        Number(b.isLow) - Number(a.isLow) ||
        (b.current?.discount_pct ?? 0) - (a.current?.discount_pct ?? 0) ||
        a.game.name.localeCompare(b.game.name, "ja"),
    );
  }, [games, wishlist, prices, today]);

  const onSale = rows.filter((r) => r.current && r.current.discount_pct > 0).length;

  return (
    <section className="panel">
      <div className="section-head">
        <h2>🛒 ウィッシュリスト</h2>
        <span className="muted small">
          {rows.length} 本 ・ セール中 {onSale} 本
        </span>
      </div>
      <ul className="wishlist">
        {rows.map(({ game, history, current, average, isLow }) => {
          const expanded = open === game.id;
          const onSaleNow = current !== null && current.discount_pct > 0;
          return (
            <li key={game.id} className={`wish${isLow ? " low" : ""}`}>
              <button className="wish-row" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : game.id)}>
                <GameImage src={game.header_image_url} width={120} height={45} />
                <span className="wish-name">{game.name}</span>
                {/* Badges sit left of the price so every price lines up on the right edge. */}
                <span className="wish-tail">
                  {isLow && <span className="low-chip small">🏆 最安値</span>}
                  {onSaleNow && <span className="discount">-{current.discount_pct}%</span>}
                  <span className="wish-price">
                    {current ? (
                      <>
                        {onSaleNow && <s className="muted small">{formatPrice(current.regular_price, current.currency)}</s>}
                        <strong>{formatPrice(current.price, current.currency)}</strong>
                      </>
                    ) : (
                      <span className="muted small">価格なし</span>
                    )}
                  </span>
                </span>
              </button>
              {expanded && (
                <div className="wish-detail">
                  <p className="small muted">
                    {game.lowest_price !== null && `最安値 ${formatPrice(game.lowest_price, game.lowest_price_currency ?? "JPY")}`}
                    {average !== null && current && ` ・ 1年の平均 ${formatPrice(Math.round(average), current.currency)}`}
                    {current?.sale_ends_at &&
                      ` ・ セール終了 ${formatJst(current.sale_ends_at, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`}
                    {game.steam_appid && (
                      <>
                        {" ・ "}
                        <a href={`https://store.steampowered.com/app/${game.steam_appid}/`} target="_blank" rel="noreferrer">
                          ストアを開く
                        </a>
                      </>
                    )}
                  </p>
                  <Suspense fallback={<p className="muted small">グラフを読み込み中…</p>}>
                    <PriceChart rows={history} today={today} lowest={game.lowest_price} average={average} />
                  </Suspense>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
