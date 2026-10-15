const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const port = Number(process.env.PORT || 4318);
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};
http
  .createServer((req, res) => {
    let file;
    try {
      const pathname = decodeURIComponent(
        new URL(req.url, "http://localhost").pathname,
      );
      file = path.resolve(
        root,
        "." + (pathname === "/" ? "/frontend/index.html" : pathname),
      );
    } catch {
      res.writeHead(400);
      return res.end("Bad request");
    }
    if (!file.startsWith(root + path.sep)) {
      res.writeHead(403);
      return res.end();
    }
    // Only the new frontend and the specified common UI widget are served.
    if (
      !file.startsWith(path.join(root, "frontend") + path.sep) &&
      file !== path.join(root, "docs", "ui", "loco-guide.js")
    ) {
      res.writeHead(404);
      return res.end();
    }
    fs.readFile(file, (error, data) => {
      if (error) {
        res.writeHead(404);
        return res.end("Not found");
      }
      res.setHeader(
        "Content-Type",
        types[path.extname(file)] || "application/octet-stream",
      );
      res.setHeader("Cache-Control", "no-store");
      res.end(data);
    });
  })
  .listen(port, "127.0.0.1", () =>
    console.log(`LOCO UI: http://127.0.0.1:${port}/frontend/index.html`),
  );
