import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

import { runCrawlerCommand } from "@/server/crawler-cli";

const ROOT_DIR = process.cwd();
const READONLY_SETTINGS_PATH = path.join(ROOT_DIR, "config", "settings.yaml");
const READONLY_SEEDS_PATH = path.join(ROOT_DIR, "data", "seeds.txt");
const RUNTIME_ROOT = path.join("/tmp", "onionnetwork-runtime");
const RUNTIME_DATA_DIR = path.join(RUNTIME_ROOT, "data");
const RUNTIME_EXPORT_DIR = path.join(RUNTIME_DATA_DIR, "exports");
const RUNTIME_LOG_DIR = path.join(RUNTIME_ROOT, "logs");
const RUNTIME_DB_PATH = path.join(RUNTIME_DATA_DIR, "onion_graph.db");
const RUNTIME_SETTINGS_PATH = path.join(RUNTIME_ROOT, "settings.yaml");
const RUNTIME_SEEDS_PATH = path.join(RUNTIME_DATA_DIR, "seeds.txt");
const VISUALIZATION_PATH = path.join(RUNTIME_EXPORT_DIR, "service_interactive.html");
const DB_FILES = [RUNTIME_DB_PATH, `${RUNTIME_DB_PATH}-shm`, `${RUNTIME_DB_PATH}-wal`];

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
  await rm(RUNTIME_EXPORT_DIR, { recursive: true, force: true });
  await rm(RUNTIME_LOG_DIR, { recursive: true, force: true });
  await mkdir(RUNTIME_DATA_DIR, { recursive: true });
  await mkdir(RUNTIME_EXPORT_DIR, { recursive: true });
  await mkdir(RUNTIME_LOG_DIR, { recursive: true });
}

async function prepareRuntimeFiles() {
  const settingsRaw = await readFile(READONLY_SETTINGS_PATH, "utf-8");
  const runtimeSettings = settingsRaw
    .replace(/^database_path:.*$/m, `database_path: "${RUNTIME_DB_PATH}"`)
    .replace(/^export_dir:.*$/m, `export_dir: "${RUNTIME_EXPORT_DIR}"`)
    .replace(/^log_dir:.*$/m, `log_dir: "${RUNTIME_LOG_DIR}"`);

  const seedsRaw = await readFile(READONLY_SEEDS_PATH, "utf-8");
  await writeFile(RUNTIME_SETTINGS_PATH, runtimeSettings, "utf-8");
  await writeFile(RUNTIME_SEEDS_PATH, seedsRaw, "utf-8");
}

async function runRuntimeCommand(command, args = []) {
  return runCrawlerCommand(command, ["--config", RUNTIME_SETTINGS_PATH, ...args]);
}

function appendCommandLog(job, result) {
  const merged = [result.command, result.stdout, result.stderr].filter(Boolean).join("\n");
  job.logs.push(merged);
}

async function runSequence(job) {
  try {
    setStep(job, "reset");
    await resetCrawlerState();
    await prepareRuntimeFiles();

    setStep(job, "init");
    appendCommandLog(job, await runRuntimeCommand("init-db"));

    setStep(job, "import");
    appendCommandLog(job, await runRuntimeCommand("import-seeds", ["--seeds", RUNTIME_SEEDS_PATH]));

    setStep(job, "crawl");
    appendCommandLog(job, await runRuntimeCommand("crawl"));

    setStep(job, "export");
    appendCommandLog(job, await runRuntimeCommand("export-graph", ["--level", "service"]));

    setStep(job, "visualize");
    appendCommandLog(
      job,
      await runRuntimeCommand("visualize", ["--level", "service", "--max-nodes", "500"])
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
