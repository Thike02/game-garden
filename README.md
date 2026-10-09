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

# 今日セール中のウィッシュリストのゲームを Discord に通知する（sync-wishlist のあとに実行）
uv run game-garden notify-sales
# 送らずに内容だけ確認する
uv run game-garden notify-sales --dry-run

# テスト
uv run pytest
```

価格は Steam ストア（`STEAM_COUNTRY_CODE` の国）の価格だけを記録します。同じセットの商品を持っていると安くなる「バンドル割引」はセールではないので、割引前の価格で記録します。

セールの通知は、割引率が `NOTIFY_MIN_DISCOUNT`（標準は20%）以上か、セール中で過去最安値以下のゲームが対象です。同じセールでは、値段がさらに下がらない限り一度しか通知しません。メッセージには、Steam での過去最安値と、直近1年の平均価格との比較も載せます。平均価格は、価格が変わるまで同じ値段が続いていたものとして、1日ずつ数えて計算します。

## 定期実行（GitHub Actions）

[.github/workflows/daily.yml](.github/workflows/daily.yml) が毎朝4時（日本時間）に `sync-steam` → `sync-wishlist` → `notify-sales` を実行します。どれかが失敗しても残りは実行し、最後に失敗したものを Discord に知らせます。Actions のページから手動でも実行できます。

リポジトリの Settings > Secrets and variables > Actions に、次の Secrets を登録してください。

- `STEAM_API_KEY`
- `STEAM_ID`
- `ITAD_API_KEY`
- `DISCORD_WEBHOOK_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

GitHub CLI を使うなら、`.env` からまとめて登録できます。

```sh
gh secret set -f .env
```

この場合、`.env` に書いてある値は全部 Secrets になります。`SUPABASE_ANON_KEY` などの使わない値も一緒に入りますが、問題はありません。

public リポジトリでは、60日間何も動きがないと定期実行が止まってしまいます。それを防ぐために、ワークフローの中で keepalive も実行しています。

## 公開ページ

[web/](web/) は React + Vite の公開ページです。`main` の `web/` が更新されると、GitHub Actions（[.github/workflows/pages.yml](.github/workflows/pages.yml)）がビルドして GitHub Pages に公開します。データはブラウザから Supabase を `anon` キーで直接読むので、毎日の更新のたびにページを作り直す必要はありません。

公開ページのビルドには、Secrets の `SUPABASE_URL` に加えて `SUPABASE_ANON_KEY` も必要です。

手元で動かすときは、`web/.env.example` をコピーして `web/.env.local` を作ります。

```sh
cd web
npm install
npm run dev
npm test
```

`?player=<SteamID64>` を付けると、表示するプレイヤーを選べます。付けないときは、最初に登録されたプレイヤーを表示します。

### 公開範囲

`players` の公開設定で、公開ページに出すものを決めます。この制限は Supabase の RLS でかけているので、API を直接読んでも非公開のデータは見えません。

| 列 | 意味 | 新しく追加したプレイヤー |
|---|---|---|
| `is_public` | このプレイヤーを公開するか | 非公開 |
| `show_playtime` | プレイ時間と、プレイ時間の草を出すか | 非公開 |
| `show_wishlist` | ウィッシュリストと価格を出すか | 非公開 |

## ローカル管理画面

```sh
uv run game-garden admin
```

自分の PC だけで開ける管理画面（`http://127.0.0.1:8765/`）がブラウザで開きます。`.env` の service_role キーを使うので、ほかの PC からは開けないようにしています。

- **設定**：キーを入れて、実際に使えるか確かめてから `.env` に保存します。`.env` がないときやキーが足りないときは、最初にこの画面が開きます。ボタンを押すと、GitHub の Secrets にも登録できます（`gh` が必要です）。
- **Steam 以外のゲーム**：Switch や PS のゲームなどを手で登録・更新します。実績は「数と解除した数」だけを記録します。画像は URL を入れるか、画像ファイル（JPEG・PNG・WebP・GIF、5MB まで）を選びます。ファイルは Supabase Storage の `game-images` に保存されます。
- **Steam の一覧に出てこないゲーム**：遊んだことのない無料ゲームなど、持っていても Steam Web API の所有ゲーム一覧に出てこないゲームを追加します。実績はプロフィールの実績ページから読み取り、プレイ時間は手で入れます。「候補を探す」では、この PC の Steam フォルダの記録から候補を探します。
- ゲームごとに、公開ページに出すかどうかを選べます。この設定も Supabase の RLS でかけています。

プロフィールの実績ページの読み取りは公式の API ではないので、Steam がページを変えると動かなくなることがあります。毎日の自動更新では使わず、管理画面の「実績を更新」ボタンを押したときだけ読み取ります。
