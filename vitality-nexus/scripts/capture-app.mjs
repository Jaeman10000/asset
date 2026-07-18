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
    totals: [...document.querySelectorAll('.totals-row .total-card .amt')].map((e) => e.textContent),
    holdings: document.querySelectorAll('.mini-holding').length,
    sparks: document.querySelectorAll('.mini-holding .spark').length,
    rankRows: document.querySelectorAll('.rank-row').length,
    readoutRows: document.querySelectorAll('.readout-row').length,
    totalText: document.querySelector('.heart-center-info .total')?.textContent,
  }));
  console.log(JSON.stringify(info), '->', out);

  // 호버 검증: 첫 KR 종목 위에 마우스 → Truth Layer 수급 4바 확인
  const row = await page.$('.mini-holding');
  if (row) {
    await row.hover();
    await new Promise((r) => setTimeout(r, 400));
    const hoverInfo = await page.evaluate(() => ({
      truthCard: !!document.querySelector('.truth-card'),
      invBars: document.querySelectorAll('.truth-card .inv-row').length,
      head: document.querySelector('.truth-card .truth-head')?.textContent,
    }));
    console.log('hover:', JSON.stringify(hoverInfo));
    await page.screenshot({ path: out.replace(/\.png$/, '-hover.png') });
  }
} finally {
  await browser.close();
}
