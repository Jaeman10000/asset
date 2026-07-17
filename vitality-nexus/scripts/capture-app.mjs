// 실행 중인 dev 서버(localhost:5173) + 백엔드(8787)를 헤드리스로 캡처.
// 사용: node scripts/capture-app.mjs <outPng>
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = CHROME_CANDIDATES.find((p) => existsSync(p));
if (!executablePath) {
  console.error('Chrome/Edge를 찾지 못했습니다.');
  process.exit(1);
}

const out = process.argv[2] ?? './app.png';
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: [
    '--no-sandbox',
    '--enable-unsafe-swiftshader',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--window-size=1440,900',
  ],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') console.log('[console.error]', m.text());
  });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 10000)); // 폴링 + 3D 안정화
  await page.screenshot({ path: out });
  const info = await page.evaluate(() => ({
    status: document.querySelector('.status-line')?.textContent,
    cards: document.querySelectorAll('.glass-card').length,
    totals: [...document.querySelectorAll('.totals-row .stat-value')].map((e) => e.textContent),
    posRows: document.querySelectorAll('.pos-row').length,
  }));
  console.log(JSON.stringify(info), '->', out);
} finally {
  await browser.close();
}
