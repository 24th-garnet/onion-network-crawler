import { getCrawlJob } from "@/server/crawl-orchestrator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const remoteBaseUrl = process.env.REMOTE_CRAWLER_API_BASE_URL;
  if (remoteBaseUrl) {
    const response = await fetch(`${remoteBaseUrl.replace(/\/$/, "")}/crawl/result`, {
      method: "GET",
      cache: "no-store"
    });
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type": "text/html; charset=utf-8"
      }
    });
  }

  const job = getCrawlJob();
  if (!job || job.status !== "done" || !job.visualizationHtml) {
    return new Response("No visualization available", { status: 404 });
  }

  return new Response(job.visualizationHtml, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8"
    }
  });
}
