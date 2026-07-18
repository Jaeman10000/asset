// 심장 영역 마우스 드래그 → OrbitControls가 카메라를 돌리는지 검증.
// window.__camPos(카메라 위치)를 드래그 전/후로 비교한다.
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
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--window-size=1440,900'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));

  const before = await page.evaluate(() => window.__camPos);

  // 화면 정중앙(심장 위)에서 가로로 드래그
  const cx = 720;
  const cy = 430;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) {
    await page.mouse.move(cx + i * 15, cy);
    await new Promise((r) => setTimeout(r, 16));
  }
  await page.mouse.up();
  await new Promise((r) => setTimeout(r, 500));

  const after = await page.evaluate(() => window.__camPos);
  const moved =
    before && after && (Math.abs(before[0] - after[0]) > 0.05 || Math.abs(before[2] - after[2]) > 0.05);
  console.log('camBefore=', JSON.stringify(before), 'camAfter=', JSON.stringify(after), 'ROTATED=', moved);
  await page.screenshot({ path: process.argv[2] ?? './drag.png' });
} finally {
  await browser.close();
}
