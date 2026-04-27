import { getCrawlJob } from "@/server/crawl-orchestrator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
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
