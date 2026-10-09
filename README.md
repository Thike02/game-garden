# Game Garden

Steam を中心に、持っているゲームの実績やプレイ状況、ウィッシュリストのゲームの価格の動きをまとめて記録するツールです。

- ウィッシュリストのゲームの価格推移グラフ（IsThereAnyDeal で過去の価格を補完）
- 持っているゲームの実績達成率（初回は全部取得し、以降は最近遊んだゲームだけ更新）
- レア実績をバッジとして表示
- セールで値下がりの大きいゲームを Discord に通知
- Steam 以外のゲームを手動で登録・更新
- GitHub の草のような日ごとのアクティビティ表示

## 構成

| 部分 | 技術 |
|---|---|
| データの収集 | Python (uv)、GitHub Actions で定期実行 |
| データの保存 | Supabase (Postgres) |
| 公開ページ | React + Vite、GitHub Pages |
| ローカル管理画面 | FastAPI |

公開ページは Supabase の `anon` キーを使い、RLS で読み取りだけができる設定です。書き込みは `service_role` キーを持っている収集スクリプトとローカル管理画面からだけ行います。

## セットアップ

1. 依存パッケージを入れる

   ```sh
   uv sync
   ```

2. `.env.example` をコピーして `.env` を作り、値を入れる

   ```sh
   cp .env.example .env
   ```

   Steam のプロフィールで「ゲームの詳細」を公開にしておく必要があります。公開していないと、実績やウィッシュリストを取得できません。

3. Supabase の SQL Editor で [supabase/migrations/](supabase/migrations/) の SQL を番号順に実行する

4. 設定を確認する

   ```sh
   uv run game-garden check-config
   ```

## 使い方

```sh
# Steam の所有ゲームと実績を同期する
# 初回は全部のゲームを取得し、以降は前回から遊んだゲームだけ更新する
uv run game-garden sync-steam

# 全部のゲームの実績を取り直す
uv run game-garden sync-steam --full

# 試しに数本だけ同期する
uv run game-garden sync-steam --limit 5

# ウィッシュリストを同期して、今日の Steam の価格を記録する
# 初めて見るゲームは IsThereAnyDeal から過去の価格履歴もまとめて取り込む
uv run game-garden sync-wishlist

# テスト
uv run pytest
```

価格は Steam ストア（`STEAM_COUNTRY_CODE` の国）の価格だけを記録します。同じセットの商品を持っていると安くなる「バンドル割引」はセールではないので、割引前の価格で記録します。
