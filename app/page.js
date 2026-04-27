"use client";

import { useMemo, useState } from "react";

const INITIAL_FORM = {
  seedsText: "",
  maxPages: 20,
  maxDepth: 2,
  maxNodes: 500,
  level: "service"
};

const STAT_KEYS = [
  "services",
  "pages",
  "snapshots",
  "links",
  "queue_pending",
  "queue_done",
  "queue_failed",
  "events"
];

async function callApi(action, method = "POST", body) {
  const response = await fetch(`/api/crawler/${action}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data.result;
}

export default function HomePage() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState("準備完了。");

  const statCards = useMemo(() => {
    return STAT_KEYS.map((key) => ({
      key,
      value: stats?.parsed?.[key] ?? "-"
    }));
  }, [stats]);

  const run = async (label, action, method = "POST", body) => {
    try {
      setBusy(true);
      setLog(`${label} を実行中...`);
      const result = await callApi(action, method, body);
      const output = [result.command, result.stdout, result.stderr].filter(Boolean).join("\n");
      setLog(output || `${label} 完了`);
      if (action !== "stats") {
        const latestStats = await callApi("stats", "GET");
        setStats(latestStats);
      } else {
        setStats(result);
      }
    } catch (error) {
      setLog(`エラー: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="container">
      <section className="hero card">
        <p className="eyebrow">ONION NETWORK CRAWLER</p>
        <h1>ワインレッドの運用ダッシュボード</h1>
        <p>
          既存PythonクローラをWebから操作し、統計確認・クロール・グラフ生成を一元化します。
        </p>
      </section>

      <section className="grid stats-grid">
        {statCards.map((item) => (
          <article className="card stat-card" key={item.key}>
            <p>{item.key}</p>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="grid controls">
        <article className="card">
          <h2>初期化・Seed投入</h2>
          <label>Seeds (1行1URL)</label>
          <textarea
            value={form.seedsText}
            onChange={(event) => setForm((prev) => ({ ...prev, seedsText: event.target.value }))}
            placeholder="http://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.onion/"
            rows={8}
          />
          <div className="actions">
            <button onClick={() => run("DB初期化", "init-db")} disabled={busy}>
              init-db
            </button>
            <button
              onClick={() =>
                run("Seed投入", "import-seeds", "POST", {
                  seeds: form.seedsText.split("\n")
                })
              }
              disabled={busy}
            >
              import-seeds
            </button>
          </div>
        </article>

        <article className="card">
          <h2>クロール設定</h2>
          <label>max-pages</label>
          <input
            type="number"
            min={1}
            value={form.maxPages}
            onChange={(event) => setForm((prev) => ({ ...prev, maxPages: event.target.value }))}
          />
          <label>max-depth</label>
          <input
            type="number"
            min={0}
            value={form.maxDepth}
            onChange={(event) => setForm((prev) => ({ ...prev, maxDepth: event.target.value }))}
          />
          <div className="actions">
            <button
              onClick={() =>
                run("クロール", "crawl", "POST", {
                  maxPages: Number(form.maxPages),
                  maxDepth: Number(form.maxDepth)
                })
              }
              disabled={busy}
            >
              crawl
            </button>
            <button onClick={() => run("統計更新", "stats", "GET")} disabled={busy}>
              stats
            </button>
          </div>
        </article>

        <article className="card">
          <h2>グラフ出力</h2>
          <label>level</label>
          <select
            value={form.level}
            onChange={(event) => setForm((prev) => ({ ...prev, level: event.target.value }))}
          >
            <option value="service">service</option>
            <option value="page">page</option>
          </select>
          <label>max-nodes</label>
          <input
            type="number"
            min={10}
            value={form.maxNodes}
            onChange={(event) => setForm((prev) => ({ ...prev, maxNodes: event.target.value }))}
          />
          <div className="actions">
            <button
              onClick={() => run("グラフ書き出し", "export-graph", "POST", { level: form.level })}
              disabled={busy}
            >
              export-graph
            </button>
            <button
              onClick={() =>
                run("可視化HTML生成", "visualize", "POST", {
                  level: form.level,
                  maxNodes: Number(form.maxNodes)
                })
              }
              disabled={busy}
            >
              visualize
            </button>
          </div>
        </article>
      </section>

      <section className="card log-card">
        <h2>実行ログ</h2>
        <pre>{log}</pre>
      </section>
    </main>
  );
}
