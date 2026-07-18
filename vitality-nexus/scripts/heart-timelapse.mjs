// 심장 과발광이 시간에 따라 쌓이는지 관찰 — t=5s,30s,60s 스크린샷.
// 사용: node scripts/heart-timelapse.mjs <outPrefix> [gl] [url]
//   gl = swiftshader(기본, 유저가 보는 것) | d3d11(실제 GPU)
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = CHROME_CANDIDATES.find((p) => existsSync(p));
const prefix = process.argv[2] ?? './heart';
const gl = process.argv[3] ?? 'swiftshader';
const url = process.argv[4] ?? 'http://localhost:5173/?noveil';
const glArgs =
  gl === 'd3d11'
    ? ['--use-gl=angle', '--use-angle=d3d11']
    : ['--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'];

const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', ...glArgs, '--window-size=1440,900'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
  const marks = [5000, 30000, 60000];
  let prev = 0;
  for (const m of marks) {
    await new Promise((r) => setTimeout(r, m - prev));
    prev = m;
    const fps = await page.evaluate(() => window.__renderCount ?? -1);
    const out = `${prefix}-${m / 1000}s.png`;
    await page.screenshot({ path: out });
    console.log(`t=${m / 1000}s  renderCount=${fps}  quality=${await page.evaluate(() => window.__qualityLevel)}  -> ${out}`);
  }
} finally {
  await browser.close();
}
