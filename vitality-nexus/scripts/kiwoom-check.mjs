import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';
const CH = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = CH.find((p) => existsSync(p));
const out = process.argv[2] ?? './kiwoom.png';
const browser = await puppeteer.launch({
  executablePath, headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--window-size=1440,900'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 9000));
  // "키움 연동" 버튼 클릭
  const clicked = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === '키움 연동');
    if (btn) { btn.click(); return true; }
    return false;
  });
  await new Promise((r) => setTimeout(r, 600));
  const info = await page.evaluate(() => ({
    clicked: true,
    panel: !!document.querySelector('[aria-label="키움 증권 연동"]'),
    inputs: document.querySelectorAll('.kiwoom-field input').length,
    hasLink: !!document.querySelector('.editor-hint a[href*="openapi.kiwoom.com"]'),
  }));
  console.log('kiwoom:', JSON.stringify({ buttonFound: clicked, ...info }));
  await page.screenshot({ path: out });
} finally {
  await browser.close();
}
