/**
 * Sidecar Edge-TTS для JArbis — порт 17848.
 * POST /speak  { text, voice?, rate?, pitch? } → { ok, path }
 * GET  /ping   → { ok, backend: "node-edge-tts" }
 */
import http from "node:http";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const PORT = Number(process.env.JARBIS_EDGE_TTS_PORT || 17848);
const ROOT = fileURLToPath(new URL(".", import.meta.url));
const OUT_DIR = join(ROOT, "..", "..", "data", "temp", "edge_node");

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function runEdgeTts(text, voice, outPath, rate, pitch) {
  return new Promise((resolve, reject) => {
    const bin = join(ROOT, "node_modules", ".bin", "edge-tts");
    const args = ["--voice", voice, "--text", text, "--write-media", outPath];
    if (rate) args.push("--rate", rate);
    if (pitch) args.push("--pitch", pitch);
    const proc = spawn(bin, args, { shell: true, windowsHide: true });
    let err = "";
    proc.stderr.on("data", (d) => (err += d.toString()));
    proc.on("close", (code) => {
      if (code === 0) resolve(outPath);
      else reject(new Error(err || `edge-tts exit ${code}`));
    });
  });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/ping") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: true, backend: "node-edge-tts", port: PORT }));
      return;
    }
    if (req.method === "POST" && req.url === "/speak") {
      const raw = await readBody(req);
      const body = JSON.parse(raw || "{}");
      const text = String(body.text || "").trim();
      if (!text) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: "empty text" }));
        return;
      }
      const voice = body.voice || "ru-RU-DmitryNeural";
      const rate = body.rate || "+0%";
      const pitch = body.pitch || "+0Hz";
      await mkdir(OUT_DIR, { recursive: true });
      const outPath = join(OUT_DIR, `edge_${randomUUID()}.mp3`);
      await runEdgeTts(text, voice, outPath, rate, pitch);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: true, path: outPath }));
      return;
    }
    res.writeHead(404);
    res.end("not found");
  } catch (e) {
    res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ ok: false, error: String(e.message || e) }));
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[edge-tts-node] 127.0.0.1:${PORT}`);
});
