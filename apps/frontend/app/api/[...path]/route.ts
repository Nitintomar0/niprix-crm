import { NextRequest } from "next/server";

const backendUrl = (process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const FORWARDED_HEADERS = ["accept", "authorization", "content-type"];

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest) {
  // With skipTrailingSlashRedirect enabled, pathname retains Django's required
  // trailing slash. Do not reconstruct it from the catch-all route parameter.
  const target = `${backendUrl}${request.nextUrl.pathname}${request.nextUrl.search}`;
  const headers = new Headers();
  FORWARDED_HEADERS.forEach((name) => {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  });

  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return Response.json(
      { detail: "The local API server is unavailable. Check that Django is running." },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  ["content-type", "cache-control", "www-authenticate"].forEach((name) => {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  });

  return new Response(response.body, { status: response.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
