import { NextResponse } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function filterHeaders(headers) {
  const out = new Headers();
  for (const [key, value] of headers.entries()) {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      out.set(key, value);
    }
  }
  return out;
}

async function proxy(req, paramsPromise) {
  const backendBase = process.env.BACKEND_URL || "http://13.60.168.165:8000";
  const params = await paramsPromise;
  const path = Array.isArray(params?.path) ? params.path.join("/") : "";
  const target = new URL(`/api/${path}`, backendBase);
  target.search = req.nextUrl.search;

  const incomingHeaders = filterHeaders(req.headers);
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();

  const upstream = await fetch(target, {
    method: req.method,
    headers: incomingHeaders,
    body,
  });

  const respHeaders = filterHeaders(upstream.headers);
  const respBody = await upstream.arrayBuffer();

  return new NextResponse(respBody, {
    status: upstream.status,
    headers: respHeaders,
  });
}

export async function GET(req, ctx) {
  return proxy(req, ctx.params);
}

export async function POST(req, ctx) {
  return proxy(req, ctx.params);
}

export async function PUT(req, ctx) {
  return proxy(req, ctx.params);
}

export async function PATCH(req, ctx) {
  return proxy(req, ctx.params);
}

export async function DELETE(req, ctx) {
  return proxy(req, ctx.params);
}

export async function OPTIONS() {
  return new NextResponse(null, { status: 204 });
}
