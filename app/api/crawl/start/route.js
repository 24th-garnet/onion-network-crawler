import { startCrawlJob } from "@/server/crawl-orchestrator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  const job = startCrawlJob();
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
