// Static file server for the built dashboard (dist/) that ALSO reverse-proxies
// /api/* to the backend API (default :8080). Running both behind one port is
// required under the Cloud9/VFS preview proxy, which only exposes a single
// port to the browser — so SSE/API calls to a second port would 503.
//
// Usage:  node serve.mjs [port] [dir] [apiPort]
import { createServer, request as httpRequest } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const PORT = Number(process.argv[2] || 8081);
const ROOT = process.argv[3] || "dist";
const API_PORT = Number(process.argv[4] || process.env.API_PORT || 8080);
const API_HOST = process.env.API_HOST || "127.0.0.1";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".woff2": "font/woff2",
  ".map": "application/json; charset=utf-8",
};

// Reverse-proxy an /api request to the backend. Streams the response through
// unbuffered so Server-Sent Events (/api/stream) work in real time.
function proxyApi(req, res) {
  const headers = { ...req.headers, host: `${API_HOST}:${API_PORT}` };
  delete headers["connection"];
  delete headers["keep-alive"];

  const upstream = httpRequest(
    { host: API_HOST, port: API_PORT, path: req.url, method: req.method, headers },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers);
      up.pipe(res);
      up.on("end", () => res.end());
    }
  );
  upstream.on("error", () => {
    if (!res.headersSent) res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "api upstream unreachable" }));
  });
  // Only tear down the upstream if the client aborts early (frees SSE threads).
  res.on("close", () => {
    if (!res.writableEnded) upstream.destroy();
  });
  // Forward a request body for POST/PUT; GET/HEAD have none.
  if (req.method === "POST" || req.method === "PUT" || req.method === "PATCH") {
    req.pipe(upstream);
  } else {
    upstream.end();
  }
}

const server = createServer(async (req, res) => {
  const urlNoQuery = (req.url || "/").split("?")[0];

  // Reverse-proxy the API (JSON + SSE) so a single port serves everything.
  if (urlNoQuery.startsWith("/api/")) {
    return proxyApi(req, res);
  }

  try {
    let urlPath = decodeURIComponent(urlNoQuery);
    if (urlPath === "/" || urlPath.endsWith("/")) urlPath += "index.html";
    // Prevent path traversal.
    const safe = normalize(urlPath).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(process.cwd(), ROOT, safe);
    const ext = extname(filePath);

    const data = await readFile(filePath);
    const type = MIME[ext] || "application/octet-stream";
    res.writeHead(200, {
      "Content-Type": type,
      "Cache-Control": "no-cache",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(data);
  } catch {
    // Asset requests (hashed JS/CSS/images) must 404 when missing so a stale
    // cached HTML referencing an old chunk fails loudly instead of receiving
    // index.html (HTML served as .css breaks silently). Only HTML navigations
    // fall back to index.html for SPA client-routing.
    const isAsset = /\.[a-z0-9]+$/i.test(urlNoQuery) && !urlNoQuery.endsWith(".html");
    if (isAsset) {
      res.writeHead(404, { "Content-Type": "text/plain", "Cache-Control": "no-cache" });
      res.end("Not found");
      return;
    }
    try {
      const data = await readFile(join(process.cwd(), ROOT, "index.html"));
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache" });
      res.end(data);
    } catch {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not found");
    }
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Serving ${ROOT}/ at http://0.0.0.0:${PORT}/  (proxying /api -> ${API_HOST}:${API_PORT})`);
});
