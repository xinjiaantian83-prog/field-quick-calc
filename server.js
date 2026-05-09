const http = require("node:http");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const PORT = Number(process.env.PORT || 3003);
const HOST = process.env.HOST || "0.0.0.0";

const staticTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

function sendJson(response, status, payload) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

function getLanUrls(port) {
  return Object.values(os.networkInterfaces())
    .flat()
    .filter((network) => network && network.family === "IPv4" && !network.internal)
    .map((network) => `http://${network.address}:${port}`);
}

async function readJson(request) {
  return new Promise((resolve, reject) => {
    let rawBody = "";
    let size = 0;

    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > 5_000_000) {
        reject(new Error("Input is too large"));
        request.destroy();
        return;
      }

      rawBody += chunk.toString();
    });

    request.on("end", () => {
      try {
        resolve(rawBody ? JSON.parse(rawBody) : {});
      } catch (error) {
        reject(error);
      }
    });

    request.on("error", reject);
  });
}

async function serveStatic(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
  const filePath = path.normalize(path.join(__dirname, pathname));

  if (!filePath.startsWith(__dirname) || !staticTypes[path.extname(filePath)]) {
    response.writeHead(404);
    response.end("Not found");
    return;
  }

  try {
    const file = await fs.readFile(filePath);
    response.writeHead(200, {
      "Content-Type": staticTypes[path.extname(filePath)],
      "Cache-Control": "no-store",
    });
    response.end(file);
  } catch {
    response.writeHead(404);
    response.end("Not found");
  }
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (request.method === "POST" && url.pathname === "/api/generate-image") {
    try {
      await readJson(request);
      sendJson(response, 501, {
        error: "AI画像生成APIは未接続です。MVPではフロント側のモック生成を使用します。",
      });
    } catch (error) {
      sendJson(response, 400, { error: error.message });
    }
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/inpaint-removal") {
    try {
      await readJson(request);
      sendJson(response, 501, {
        error: "撤去インペイントAPIは未接続です。MVPではフロント側のモック撤去を使用します。",
      });
    } catch (error) {
      sendJson(response, 400, { error: error.message });
    }
    return;
  }

  if (request.method === "GET") {
    await serveStatic(request, response);
    return;
  }

  response.writeHead(405);
  response.end("Method not allowed");
});

server.listen(PORT, HOST, () => {
  const lanUrls = getLanUrls(PORT);

  console.log(`Exterior AI Field Preview running`);
  console.log(`Mac: http://127.0.0.1:${PORT}`);
  console.log(`iPhone Safari: ${lanUrls[0] || `http://MacのLAN内IPアドレス:${PORT}`}`);
  console.log("iPhoneはMacと同じWi-Fiに接続して、このURLをSafariで開いてください。");

  if (lanUrls.length > 1) {
    console.log(`Other LAN URLs: ${lanUrls.slice(1).join(", ")}`);
  }
});
