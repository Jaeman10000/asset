// 완전 새 로드(HMR 캐시 없음)에서 콘솔/페이지 에러가 없는지 확인.
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
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', (e) => errors.push('[pageerror] ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('[console.error] ' + m.text());
  });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 9000));
  const nodes = await page.evaluate(() => ({
    ringLabels: document.querySelectorAll('canvas').length, // 씬 캔버스 존재
    quality: window.__qualityLevel,
    camPos: window.__camPos,
  }));
  console.log('errors=', errors.length ? JSON.stringify(errors) : 'NONE');
  console.log('scene=', JSON.stringify(nodes));
} finally {
  await browser.close();
}
