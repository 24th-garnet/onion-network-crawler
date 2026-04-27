"use client";

import { useEffect, useMemo, useState } from "react";

export default function HomePage() {
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);

  const progress = useMemo(() => {
    if (!job) {
      return 0;
    }
    return Number(job.progress || 0);
  }, [job]);

  const isRunning = job?.status === "running";
  const isError = job?.status === "error";

  useEffect(() => {
    let timer;

    async function pollStatus() {
      try {
        const response = await fetch("/api/crawl/status", { cache: "no-store" });
        const data = await response.json();
        if (data?.ok) {
          setJob(data.job);
        }
      } catch (_error) {
        // Polling failure is treated as transient; the next cycle retries.
      }
    }

    pollStatus();

    if (isRunning) {
      timer = setInterval(pollStatus, 1200);
    }

    return () => {
      if (timer) {
        clearInterval(timer);
      }
    };
  }, [isRunning]);

  async function startCrawl() {
    try {
      setLoading(true);
      const response = await fetch("/api/crawl/start", {
        method: "POST"
      });
      const data = await response.json();
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || "Start failed");
      }
      setJob((prev) => ({
        ...prev,
        ...data.job
      }));
    } catch (error) {
      setJob({
        status: "error",
        progress: 0,
        message: "開始に失敗しました",
        error: error instanceof Error ? error.message : "Unknown error",
        logs: []
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <section className="hero card">
        <p className="eyebrow">ONION NETWORK CRAWLER</p>
        <h1>ワンクリック・クロール</h1>
        <p>
          毎回リセットし、`data/seeds.txt` (Hidden Wiki) からクロールして可視化まで自動実行します。
        </p>
        <div className="actions single-action">
          <button onClick={startCrawl} disabled={loading || isRunning}>
            {isRunning ? "クロール実行中..." : "クロール開始"}
          </button>
        </div>
        <div className="progress-wrap">
          <div className="progress-meta">
            <span>{job?.message || "待機中"}</span>
            <strong>{progress}%</strong>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          {isError ? <p className="error-text">エラー: {job?.error || "unknown"}</p> : null}
        </div>
      </section>

      <section className="card log-card">
        <h2>実行ログ</h2>
        <pre>{job?.logs?.length ? job.logs.join("\n\n---\n\n") : "ログはまだありません。"}</pre>
      </section>

      <section className="card viz-card">
        <h2>可視化ビュー</h2>
        {job?.visualizationHtml ? (
          <iframe
            className="viz-frame"
            title="Onion Graph Visualization"
            srcDoc={job.visualizationHtml}
            sandbox="allow-scripts allow-same-origin"
          />
        ) : (
          <div className="viz-empty">クロール完了後にここへグラフを表示します。</div>
        )}
      </section>
    </main>
  );
}
