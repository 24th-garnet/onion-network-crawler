import { startCrawlJob } from "@/server/crawl-orchestrator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const maxDepth = Number(body?.maxDepth ?? 1);
  const seedText = typeof body?.seedText === "string" ? body.seedText : "";

  const remoteBaseUrl = process.env.REMOTE_CRAWLER_API_BASE_URL;
  if (remoteBaseUrl) {
    const response = await fetch(`${remoteBaseUrl.replace(/\/$/, "")}/crawl/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ maxDepth, seedText }),
      cache: "no-store"
    });
    const payload = await response.json();
    return Response.json(payload, { status: response.status });
  }

  const job = startCrawlJob({ maxDepth, seedText });
  return Response.json({
    ok: true,
    job: {
      id: job.id,
      status: job.status,
      progress: job.progress,
      message: job.message
    }
  });
}
