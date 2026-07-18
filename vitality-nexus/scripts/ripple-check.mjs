// 진입 물결(.ripple) + 행 꿈틀(rowWobble) 적용 여부 DOM 검증 + 초기 프레임 캡처.
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
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 9000));
  // 암호화폐 카드의 마지막 행(XRP)에 왼쪽에서 진입
  const rows = await page.$$('.mini-holding');
  const target = rows[rows.length - 1];
  const box = await target.boundingBox();
  await page.mouse.move(box.x + 20, box.y + box.height / 2);
  const sample = () =>
    page.evaluate(() => {
      const rip = document.querySelector('.ripple');
      const ripCs = rip ? getComputedStyle(rip) : null;
      const m = ripCs?.transform?.match(/matrix\(([^,]+)/);
      return { scaleX: m ? +m[1] : null, opacity: ripCs?.opacity };
    });
  await new Promise((r) => setTimeout(r, 120));
  const s1 = await sample();
  await new Promise((r) => setTimeout(r, 250));
  const s2 = await sample();
  console.log('t~120ms', JSON.stringify(s1), ' t~370ms', JSON.stringify(s2));
  await page.screenshot({
    path: process.argv[2] ?? './ripple-crop.png',
    clip: { x: 8, y: 630, width: 360, height: 250 },
  });
} finally {
  await browser.close();
}
