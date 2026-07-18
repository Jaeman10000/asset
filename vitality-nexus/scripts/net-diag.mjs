// 브라우저에서 프론트가 백엔드를 왜 못 붙는지 진단 — 네트워크 요청/응답 + 콘솔.
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
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'],
});
try {
  const page = await browser.newPage();
  const reqs = [];
  page.on('requestfailed', (r) => reqs.push(`FAIL ${r.url()} :: ${r.failure()?.errorText}`));
  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api') || u.includes('8787') || u.includes('portfolio') || u.includes('health'))
      reqs.push(`${r.status()} ${u}`);
  });
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 12000));
  const state = await page.evaluate(() => ({
    boot: document.querySelector('.boot-msg')?.textContent ?? null,
    status: document.querySelector('.status-line')?.textContent ?? null,
    cards: document.querySelectorAll('.card').length,
    apiBase: window.location.origin,
  }));
  console.log('STATE:', JSON.stringify(state));
  console.log('NET:\n' + (reqs.join('\n') || '(no api requests seen)'));
  console.log('LOGS:\n' + (logs.slice(-15).join('\n') || '(none)'));
} finally {
  await browser.close();
}
