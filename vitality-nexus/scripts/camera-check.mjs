// 심장 카메라 컨트롤 검증: 휠 스크롤=확대/축소, 휠클릭 드래그=팬, 좌드래그=회전.
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';
const CHROME = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].find((p) => existsSync(p));
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--window-size=1440,900'],
});
const dist = (p) => (p ? Math.hypot(p[0], p[1], p[2]).toFixed(3) : 'null');
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/?noveil', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));
  const cx = 720, cy = 430;

  const before = await page.evaluate(() => window.__camPos);
  // 휠 스크롤(확대) — 심장 위에서
  await page.mouse.move(cx, cy);
  for (let i = 0; i < 6; i++) { await page.mouse.wheel({ deltaY: -120 }); await new Promise((r) => setTimeout(r, 30)); }
  await new Promise((r) => setTimeout(r, 400));
  const afterZoom = await page.evaluate(() => window.__camPos);

  // 휠클릭(가운데 버튼) 드래그 = 팬
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'middle' });
  for (let i = 1; i <= 8; i++) { await page.mouse.move(cx, cy + i * 10); await new Promise((r) => setTimeout(r, 16)); }
  await page.mouse.up({ button: 'middle' });
  await new Promise((r) => setTimeout(r, 400));
  const afterPan = await page.evaluate(() => window.__camPos);

  const zoomed = before && afterZoom && Math.abs(+dist(before) - +dist(afterZoom)) > 0.1;
  const panned = afterZoom && afterPan && (Math.abs(afterZoom[1] - afterPan[1]) > 0.05 || Math.abs(afterZoom[0] - afterPan[0]) > 0.05);
  console.log(`dist before=${dist(before)} afterZoom=${dist(afterZoom)}  ZOOM=${zoomed}`);
  console.log(`pan camY ${afterZoom?.[1]} -> ${afterPan?.[1]}  PAN=${panned}`);
} finally {
  await browser.close();
}
