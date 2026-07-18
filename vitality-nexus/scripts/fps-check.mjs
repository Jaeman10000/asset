// 실제 GPU(ANGLE d3d11)로 dev 서버 fps 측정 — 홀로그램 링 추가 후 성능 확인
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = CHROME_CANDIDATES.find((p) => existsSync(p));

const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=d3d11', '--window-size=1440,900'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 6000)); // 3D 안정화
  const fps = await page.evaluate(
    () =>
      new Promise((resolve) => {
        const w = window;
        const start = w.__renderCount ?? 0;
        setTimeout(() => resolve(((w.__renderCount ?? 0) - start) / 5), 5000);
      }),
  );
  const quality = await page.evaluate(() => window.__qualityLevel);
  console.log(`fps=${fps} quality=${quality}`);
} finally {
  await browser.close();
}
