import { mkdir, readFile, rm } from "node:fs/promises";
import path from "node:path";

import { runCrawlerCommand } from "@/server/crawler-cli";

const ROOT_DIR = process.cwd();
const EXPORT_DIR = path.join(ROOT_DIR, "data", "exports");
const LOG_DIR = path.join(ROOT_DIR, "logs");
const VISUALIZATION_PATH = path.join(EXPORT_DIR, "service_interactive.html");
const DB_FILES = [
  path.join(ROOT_DIR, "data", "onion_graph.db"),
  path.join(ROOT_DIR, "data", "onion_graph.db-shm"),
  path.join(ROOT_DIR, "data", "onion_graph.db-wal")
];

const STEP_PLAN = [
  { key: "reset", label: "既存データをリセット", progress: 15 },
  { key: "init", label: "DB初期化", progress: 30 },
  { key: "import", label: "seeds投入(hidden wiki)", progress: 45 },
  { key: "crawl", label: "クロール実行", progress: 75 },
  { key: "export", label: "グラフ出力", progress: 88 },
  { key: "visualize", label: "可視化HTML生成", progress: 96 }
];

let currentJob = null;

function newJob() {
  return {
    id: `crawl-${Date.now()}`,
    status: "running",
    progress: 5,
    message: "ジョブを開始しました",
    logs: [],
    visualizationHtml: null,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    error: null
  };
}

function setStep(job, stepKey) {
  const step = STEP_PLAN.find((item) => item.key === stepKey);
  if (!step) {
    return;
  }
  job.progress = step.progress;
  job.message = step.label;
}

async function resetCrawlerState() {
  for (const file of DB_FILES) {
    await rm(file, { force: true });
  }
  await rm(EXPORT_DIR, { recursive: true, force: true });
  await rm(LOG_DIR, { recursive: true, force: true });
  await mkdir(EXPORT_DIR, { recursive: true });
  await mkdir(LOG_DIR, { recursive: true });
}

function appendCommandLog(job, result) {
  const merged = [result.command, result.stdout, result.stderr].filter(Boolean).join("\n");
  job.logs.push(merged);
}

async function runSequence(job) {
  try {
    setStep(job, "reset");
    await resetCrawlerState();

    setStep(job, "init");
    appendCommandLog(job, await runCrawlerCommand("init-db"));

    setStep(job, "import");
    appendCommandLog(job, await runCrawlerCommand("import-seeds", ["--seeds", "data/seeds.txt"]));

    setStep(job, "crawl");
    appendCommandLog(job, await runCrawlerCommand("crawl"));

    setStep(job, "export");
    appendCommandLog(job, await runCrawlerCommand("export-graph", ["--level", "service"]));

    setStep(job, "visualize");
    appendCommandLog(
      job,
      await runCrawlerCommand("visualize", ["--level", "service", "--max-nodes", "500"])
    );

    job.visualizationHtml = await readFile(VISUALIZATION_PATH, "utf-8");
    job.progress = 100;
    job.status = "done";
    job.message = "可視化まで完了しました";
    job.finishedAt = new Date().toISOString();
  } catch (error) {
    job.status = "error";
    job.error = error instanceof Error ? error.message : "Unknown error";
    job.message = "処理が失敗しました";
    job.finishedAt = new Date().toISOString();
  }
}

export function startCrawlJob() {
  if (currentJob && currentJob.status === "running") {
    return currentJob;
  }
  currentJob = newJob();
  runSequence(currentJob);
  return currentJob;
}

export function getCrawlJob() {
  return currentJob;
}
