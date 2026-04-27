import { getCrawlJob } from "@/server/crawl-orchestrator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const remoteBaseUrl = process.env.REMOTE_CRAWLER_API_BASE_URL;
  if (remoteBaseUrl) {
    const response = await fetch(`${remoteBaseUrl.replace(/\/$/, "")}/crawl/status`, {
      method: "GET",
      cache: "no-store"
    });
    const payload = await response.json();
    return Response.json(payload, { status: response.status });
  }

  const job = getCrawlJob();
  if (!job) {
    return Response.json({
      ok: true,
      job: null
    });
  }

  return Response.json({
    ok: true,
    job: {
      id: job.id,
      status: job.status,
      progress: job.progress,
      message: job.message,
      error: job.error,
      startedAt: job.startedAt,
      finishedAt: job.finishedAt,
      logs: job.logs,
      visualizationHtml: job.visualizationHtml
    }
  });
}
