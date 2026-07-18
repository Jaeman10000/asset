// dist/를 Tauri 프로덕션과 동일한 CSP 헤더로 서빙해서 CSP 위반을 재현·진단.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const DIST = new URL('../dist/', import.meta.url).pathname.replace(/^\//, '');
const PORT = 5199;

// tauri.conf.json의 CSP와 동일
const CSP =
  "default-src 'self'; img-src 'self' data: asset: http://asset.localhost blob:; " +
  "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; " +
  "connect-src 'self' ipc: http://ipc.localhost http://localhost:8787 http://127.0.0.1:8787 " +
  "https://query1.finance.yahoo.com https://api.upbit.com https://api.bithumb.com";

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.svg': 'image/svg+xml', '.glb': 'model/gltf-binary', '.png': 'image/png',
  '.json': 'application/json', '.wasm': 'application/wasm',
};

createServer(async (req, res) => {
  let path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (path === '/') path = '/index.html';
  const file = normalize(join(DIST, path));
  res.setHeader('Content-Security-Policy', CSP);
  try {
    const data = await readFile(file);
    res.setHeader('Content-Type', MIME[extname(file)] ?? 'application/octet-stream');
    res.end(data);
  } catch {
    // SPA 폴백
    try {
      const idx = await readFile(join(DIST, 'index.html'));
      res.setHeader('Content-Type', 'text/html');
      res.end(idx);
    } catch {
      res.statusCode = 404;
      res.end('not found');
    }
  }
}).listen(PORT, () => console.log(`serving dist with Tauri CSP → http://localhost:${PORT}`));
