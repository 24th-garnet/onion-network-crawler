import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

const execFileAsync = promisify(execFile);

const ROOT_DIR = process.cwd();
const PYTHON_MODULE_ENTRY = ["-m", "src.main"];

function parseStatsOutput(stdout) {
  const stats = {};
  for (const line of stdout.split("\n")) {
    if (!line.includes(":")) {
      continue;
    }
    const [key, rawValue] = line.split(":");
    const value = Number(rawValue.trim());
    stats[key.trim()] = Number.isNaN(value) ? rawValue.trim() : value;
  }
  return stats;
}

export async function runCrawlerCommand(command, args = []) {
  const cliArgs = [...PYTHON_MODULE_ENTRY, command, ...args];
  const { stdout, stderr } = await execFileAsync("python", cliArgs, {
    cwd: ROOT_DIR,
    timeout: 1000 * 60 * 20,
    maxBuffer: 1024 * 1024 * 10
  });

  return {
    command: `python ${cliArgs.join(" ")}`,
    stdout,
    stderr
  };
}

export async function fetchStats() {
  const result = await runCrawlerCommand("stats");
  return {
    ...result,
    parsed: parseStatsOutput(result.stdout)
  };
}

export function seedsFilePath() {
  return path.join(ROOT_DIR, "data", "seeds.txt");
}
