// 종목 클릭 → 실시간 차트 패널 검증.
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';

const CH = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = CH.find((p) => existsSync(p));
const out = process.argv[2] ?? './chart.png';
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--window-size=1440,900'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 9000));
  const row = await page.$('.mini-holding');
  if (!row) throw new Error('no .mini-holding');
  await row.click();
  await new Promise((r) => setTimeout(r, 1200));
  const info = await page.evaluate(() => ({
    panel: !!document.querySelector('.chart-panel'),
    title: document.querySelector('.chart-panel .chart-title strong')?.textContent,
    price: document.querySelector('.chart-panel .cp-now')?.textContent,
    hasPath: !!document.querySelector('.chart-svg path'),
    live: !!document.querySelector('.chart-live'),
    foot: document.querySelector('.chart-foot')?.textContent,
  }));
  console.log('chart:', JSON.stringify(info));
  await page.screenshot({ path: out });
} finally {
  await browser.close();
}
