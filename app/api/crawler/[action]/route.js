import { writeFile } from "node:fs/promises";

import { fetchStats, runCrawlerCommand, seedsFilePath } from "@/server/crawler-cli";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function json(data, status = 200) {
  return Response.json(data, { status });
}

function formatError(error) {
  if (error?.code === "ETIMEDOUT") {
    return "処理がタイムアウトしました。対象を絞って再実行してください。";
  }
  return error instanceof Error ? error.message : "Unexpected error";
}

export async function GET(_request, { params }) {
  const { action } = await params;

  if (action !== "stats") {
    return json({ ok: false, error: "Unsupported GET action" }, 400);
  }

  try {
    const result = await fetchStats();
    return json({ ok: true, result });
  } catch (error) {
    return json({ ok: false, error: formatError(error) }, 500);
  }
}

export async function POST(request, { params }) {
  const { action } = await params;

  try {
    if (action === "init-db") {
      const result = await runCrawlerCommand("init-db");
      return json({ ok: true, result });
    }

    if (action === "import-seeds") {
      const body = await request.json().catch(() => ({}));
      const seeds = Array.isArray(body?.seeds) ? body.seeds : [];
      const cleaned = seeds.map((v) => String(v).trim()).filter(Boolean);
      if (cleaned.length) {
        await writeFile(seedsFilePath(), `${cleaned.join("\n")}\n`, "utf-8");
      }
      const result = await runCrawlerCommand("import-seeds", ["--seeds", "data/seeds.txt"]);
      return json({ ok: true, result });
    }

    if (action === "crawl") {
      const body = await request.json().catch(() => ({}));
      const maxPages = Number(body?.maxPages || 20);
      const maxDepth = Number(body?.maxDepth || 2);
      const result = await runCrawlerCommand("crawl", [
        "--max-pages",
        String(maxPages),
        "--max-depth",
        String(maxDepth)
      ]);
      return json({ ok: true, result });
    }

    if (action === "export-graph") {
      const body = await request.json().catch(() => ({}));
      const level = body?.level === "page" ? "page" : "service";
      const result = await runCrawlerCommand("export-graph", ["--level", level]);
      return json({ ok: true, result });
    }

    if (action === "visualize") {
      const body = await request.json().catch(() => ({}));
      const level = body?.level === "page" ? "page" : "service";
      const maxNodes = Number(body?.maxNodes || 500);
      const result = await runCrawlerCommand("visualize", [
        "--level",
        level,
        "--max-nodes",
        String(maxNodes)
      ]);
      return json({ ok: true, result });
    }

    return json({ ok: false, error: "Unsupported action" }, 400);
  } catch (error) {
    return json({ ok: false, error: formatError(error) }, 500);
  }
}
