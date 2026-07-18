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
  const reducedMotion = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  // 벨트(항상 도는 CSS 애니)의 transform이 시간에 따라 변하는지
  const beltAt = () => page.evaluate(() => {
    const b = document.querySelector('.fl-belt-i');
    const m = b ? getComputedStyle(b).transform.match(/matrix\(([^)]+)\)/) : null;
    const play = b ? getComputedStyle(b).animationPlayState : null;
    return { tx: m ? m[1].split(',').map((x) => +x.trim())[4] : null, play };
  });
  const b1 = await beltAt();
  await new Promise((r) => setTimeout(r, 300));
  const b2 = await beltAt();
  console.log('reducedMotion=', reducedMotion);
  console.log('belt tx t0=', JSON.stringify(b1), ' t+300=', JSON.stringify(b2));
} finally {
  await browser.close();
}
