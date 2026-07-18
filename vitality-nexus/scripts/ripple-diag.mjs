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
  const rows = await page.$$('.mini-holding');
  const target = rows[rows.length - 1];
  const box = await target.boundingBox();
  await page.mouse.move(box.x + 20, box.y + box.height / 2);
  const probe = () =>
    page.evaluate(() => {
      const anims = document.getAnimations().filter((a) => {
        const t = a.effect?.target;
        return t && t.classList && t.classList.contains('ripple');
      });
      return {
        ripples: document.querySelectorAll('.ripple').length,
        rippleAnims: anims.length,
        first: anims[0] ? { ct: Math.round(anims[0].currentTime), state: anims[0].playState } : null,
      };
    });
  await new Promise((r) => setTimeout(r, 100));
  console.log('t~100', JSON.stringify(await probe()));
  await new Promise((r) => setTimeout(r, 250));
  console.log('t~350', JSON.stringify(await probe()));
  await new Promise((r) => setTimeout(r, 250));
  console.log('t~600', JSON.stringify(await probe()));
} finally {
  await browser.close();
}
