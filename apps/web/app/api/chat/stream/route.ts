const apiBaseUrl = (
  process.env.RENDER_API_URL ?? process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function POST(request: Request): Promise<Response> {
  const upstream = await fetch(`${apiBaseUrl}/api/chat/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(request.headers.get("cookie")
        ? { Cookie: request.headers.get("cookie") as string }
        : {}),
    },
    body: await request.text(),
    cache: "no-store",
  });

  const headers = new Headers({
    "Cache-Control": "no-cache, no-transform",
    "Content-Type": "text/event-stream; charset=utf-8",
    "X-Accel-Buffering": "no",
  });
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    headers.set("Set-Cookie", setCookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
