# Onion Network Graph Crawler: Local Usage Guide

このドキュメントは、`OnionNetwork` プロジェクトを **Dockerではなくローカル環境** で実行し、Hidden Wiki などの seed から `.onion` リンクグラフをクロール・保存・可視化するための手順です。

## Web Dashboard (Next.js)

Next.js ベースのWebダッシュボードを追加しています。初期verでは、**クロール開始ボタン1つ**で次を順番に自動実行します。

1. 過去データをリセット（DB / exports / logs）
2. `data/seeds.txt`（Hidden Wiki を想定）を投入
3. クロール実行
4. グラフ出力・可視化生成
5. Webアプリ内ボックスへ可視化表示

Vercel 上で iframe に埋め込むため、可視化HTMLは PyVis の `cdn_resources=remote`（bindings をインライン、vis-network は CDN）で生成します。`local` のままだと `lib/...` 相対パスがアプリのオリジンに解決されグラフが表示されません。

### 起動方法

```bash
npm install
npm run dev
```

`http://localhost:3000` を開くと、ワインレッド基調のUIで操作できます。

### Render API サーバとして使う場合

このリポジトリは Docker で FastAPI バックエンドも起動できます。Render の Web Service では以下を使用します。

- Docker 環境でデプロイ
- 起動コマンド: Dockerfile の `CMD` を利用（`/work/scripts/start-render-api.sh`）
- ヘルスチェック: `GET /health`
- 実行API:
  - `POST /crawl/start` (`{ "maxDepth": 1, "seedText": "http://...onion/" }` のように深度やseed文字列を指定可能。`seedText` 未指定/空なら `data/seeds.txt` を使用)
  - `GET /crawl/status`

Vercel 側から Render API を使う場合は、環境変数に Render のURLを設定します。

```bash
REMOTE_CRAWLER_API_BASE_URL=https://<your-render-service>.onrender.com
```

## 1. 前提

作業ディレクトリは以下を想定します。

```bash
cd ~/Playgrounds/OnionNetwork
```

Python 環境は conda の `OnionNetwork` 環境を想定します。

```bash
conda activate OnionNetwork
```

Tor はホストOS側で起動しておきます。

```bash
sudo systemctl status tor
```

Tor SOCKS ポートは通常 `127.0.0.1:9050` です。

確認:

```bash
ss -ltnp | grep 9050
```

Tor 経由通信の確認:

```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
```

`"IsTor":true` が返ればOKです。

---

## 2. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

---

## 3. 設定ファイルの確認

`config/settings.yaml` の Tor proxy が以下になっていることを確認します。

```yaml
tor:
  proxy_url: "socks5h://127.0.0.1:9050"
```

`9050` ではなく Tor Browser の `9150` を使う場合は、以下に変更します。

```yaml
tor:
  proxy_url: "socks5h://127.0.0.1:9150"
```

---

## 4. seeds.txt の用意

`data/seeds.txt` に初期 seed を1行1URLで書きます。

```bash
nano data/seeds.txt
```

例:

```text
http://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.onion/
http://yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.onion/
```

最初は Hidden Wiki の main page だけでも動作確認できますが、実運用では 5〜10件以上の seed を推奨します。

---

## 5. DBと出力結果の完全リセット

過去の queue 状態や failed 状態を消すため、必要に応じて完全リセットします。

```bash
rm -f data/onion_graph.db*
rm -rf data/exports/*
rm -rf logs/*
```

---

## 6. DB初期化

```bash
python -m src.main init-db
```

期待される出力:

```text
Initialized DB: data/onion_graph.db
```

---

## 7. seed 投入

```bash
python -m src.main import-seeds --seeds data/seeds.txt
```

期待される出力:

```text
Imported seeds: 1
```

複数seedを入れていれば、その件数が表示されます。

---

## 8. 状態確認

```bash
python -m src.main stats
```

例:

```text
services: 0
pages: 0
snapshots: 0
links: 0
queue_pending: 1
queue_done: 0
queue_failed: 0
events: 0
```

`queue_pending` が 1 以上であれば、クロール対象が入っています。

---

## 9. クロール実行

小さく開始します。

```bash
python -m src.main crawl --max-pages 20 --max-depth 2
```

より広く探索する場合:

```bash
python -m src.main crawl --max-pages 100 --max-depth 3
```

---

## 10. クロール後の確認

```bash
python -m src.main stats
```

成功例:

```text
services: 1
pages: 2
snapshots: 2
links: 644
queue_pending: 0
queue_done: 2
queue_failed: 0
events: 646
```

`links` が増えていれば、HTMLからリンク抽出できています。

---

## 11. `.onion` リンク抽出状況の確認

```bash
sqlite3 data/onion_graph.db "
SELECT is_onion, COUNT(*)
FROM links
GROUP BY is_onion;
"
```

例:

```text
0|23
1|621
```

`is_onion=1` が `.onion` リンクです。

発見された onion host 上位を確認:

```bash
sqlite3 data/onion_graph.db "
SELECT target_onion_host, COUNT(*) AS c
FROM links
WHERE target_onion_host IS NOT NULL
GROUP BY target_onion_host
ORDER BY c DESC
LIMIT 20;
"
```

---

## 12. 発見済み onion を再クロール対象に投入

スター型グラフしか見えない場合、実際にクロール済みページが少ない可能性があります。

現在の queue 状態確認:

```bash
sqlite3 data/onion_graph.db "
SELECT depth, status, COUNT(*)
FROM crawl_queue
GROUP BY depth, status
ORDER BY depth, status;
"
```

発見済み `.onion` URL を queue に再投入:

```bash
sqlite3 data/onion_graph.db "
INSERT OR IGNORE INTO crawl_queue(
  url, onion_host, depth, priority, seed_origin,
  discovered_from_url, discovered_at, next_fetch_at, status
)
SELECT DISTINCT
  target_url,
  target_onion_host,
  1,
  20,
  'requeued_from_links',
  source_url,
  datetime('now'),
  NULL,
  'pending'
FROM links
WHERE target_onion_host IS NOT NULL
  AND target_url LIKE 'http%';
"
```

再確認:

```bash
sqlite3 data/onion_graph.db "
SELECT depth, status, COUNT(*)
FROM crawl_queue
GROUP BY depth, status
ORDER BY depth, status;
"
```

その後、再クロール:

```bash
python -m src.main crawl --max-pages 100 --max-depth 3
```

---

## 13. グラフ出力

サービス単位グラフを出力します。

```bash
python -m src.main export-graph --level service
```

出力先:

```text
data/exports/service_nodes.csv
data/exports/service_edges.csv
data/exports/service_graph.gexf
data/exports/service_graph.graphml
```

ページ単位グラフを出力する場合:

```bash
python -m src.main export-graph --level page
```

---

## 14. インタラクティブHTML可視化

```bash
python -m src.main visualize --level service --max-nodes 500
```

ブラウザで開きます。

```bash
xdg-open data/exports/service_interactive.html
```

ページ単位で可視化する場合:

```bash
python -m src.main visualize --level page --max-nodes 500
xdg-open data/exports/page_interactive.html
```

---

## 15. Gephiで確認する場合

```bash
gephi data/exports/service_graph.gexf
```

Gephiでは以下を確認します。

- PageRank
- in-degree / out-degree
- weakly connected components
- strongly connected components
- hub / indexer 候補

---

## 16. よくある問題

### 16.1 クロールが即終了する

原因: `queue_pending` が 0。

確認:

```bash
python -m src.main stats
```

対策:

```bash
python -m src.main import-seeds --seeds data/seeds.txt
```

または、発見済みリンクを再投入します。

```bash
sqlite3 data/onion_graph.db "
UPDATE crawl_queue
SET status='pending', last_error=NULL
WHERE status='failed';
"
```

---

### 16.2 seedが1件しかない

Hidden Wiki などは不安定なので、seed 1件では不十分です。`data/seeds.txt` に複数 seed を入れてください。

---

### 16.3 Dockerでは失敗するがローカルでは動く

Docker コンテナからホストの Tor SOCKS `127.0.0.1:9050` が見えていない可能性があります。

このプロジェクトでは、まずローカル conda 環境での実行を推奨します。

---

### 16.4 スター型グラフしか見えない

原因: seedページから外部 onion へのリンクは抽出できているが、外部 onion 自体をまだ十分にクロールしていない。

対策:

1. 発見済み onion を queue に再投入
2. `--max-pages` を増やして再クロール
3. 再度 `export-graph` と `visualize`

---

## 17. 最小実行コマンドまとめ

完全リセットから可視化まで:

```bash
cd ~/Playgrounds/OnionNetwork
conda activate OnionNetwork

rm -f data/onion_graph.db*
rm -rf data/exports/*
rm -rf logs/*

pip install -r requirements.txt

python -m src.main init-db
python -m src.main import-seeds --seeds data/seeds.txt
python -m src.main stats
python -m src.main crawl --max-pages 20 --max-depth 2
python -m src.main stats
python -m src.main export-graph --level service
python -m src.main visualize --level service --max-nodes 500
xdg-open data/exports/service_interactive.html
```

発見済み onion を拡張クロールする場合:

```bash
sqlite3 data/onion_graph.db "
INSERT OR IGNORE INTO crawl_queue(
  url, onion_host, depth, priority, seed_origin,
  discovered_from_url, discovered_at, next_fetch_at, status
)
SELECT DISTINCT
  target_url,
  target_onion_host,
  1,
  20,
  'requeued_from_links',
  source_url,
  datetime('now'),
  NULL,
  'pending'
FROM links
WHERE target_onion_host IS NOT NULL
  AND target_url LIKE 'http%';
"

python -m src.main crawl --max-pages 100 --max-depth 3
python -m src.main export-graph --level service
python -m src.main visualize --level service --max-nodes 500
xdg-open data/exports/service_interactive.html
```
