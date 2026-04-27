import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

const execFileAsync = promisify(execFile);

const ROOT_DIR = process.cwd();
const PYTHON_MODULE_ENTRY = ["-m", "src.main"];
const PYTHON_CANDIDATES = ["python", "python3"];
let resolvedPythonCommand = null;

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
  const pythonCommand = await resolvePythonCommand();
  const { stdout, stderr } = await execFileAsync(pythonCommand, cliArgs, {
    cwd: ROOT_DIR,
    timeout: 1000 * 60 * 20,
    maxBuffer: 1024 * 1024 * 10
  });

  return {
    command: `${pythonCommand} ${cliArgs.join(" ")}`,
    stdout,
    stderr
  };
}

async function resolvePythonCommand() {
  if (resolvedPythonCommand) {
    return resolvedPythonCommand;
  }

  for (const candidate of PYTHON_CANDIDATES) {
    try {
      await execFileAsync(candidate, ["--version"], {
        cwd: ROOT_DIR,
        timeout: 5000,
        maxBuffer: 1024 * 64
      });
      resolvedPythonCommand = candidate;
      return candidate;
    } catch (error) {
      if (error?.code === "ENOENT") {
        continue;
      }
      throw error;
    }
  }

  throw new Error(
    "Python runtime not found (tried: python, python3). Vercel Node serverless does not include Python by default."
  );
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
