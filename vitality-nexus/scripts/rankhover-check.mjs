// 랭킹 행 호버 시 Truth 카드가 랭킹 카드 왼쪽(가리지 않게)에 나오는지 검증.
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
  const rank = await page.$('.rank-row');
  await rank.hover();
  await new Promise((r) => setTimeout(r, 500));
  const info = await page.evaluate(() => {
    const card = document.querySelector('.truth-card');
    const rankCard = document.querySelector('.ranking-card');
    const row = document.querySelector('.rank-row');
    const cr = card?.getBoundingClientRect();
    const rc = rankCard?.getBoundingClientRect();
    const rr = row?.getBoundingClientRect();
    return {
      cardLeft: cr ? Math.round(cr.left) : null,
      cardRight: cr ? Math.round(cr.right) : null,
      rankCardLeft: rc ? Math.round(rc.left) : null,
      rowLeft: rr ? Math.round(rr.left) : null,
      // 카드 오른쪽 끝이 랭킹 카드 왼쪽보다 작으면 = 안 가림
      clearsRanking: cr && rc ? cr.right <= rc.left + 2 : null,
    };
  });
  console.log(JSON.stringify(info));
  await page.screenshot({ path: process.argv[2] ?? './rankhover.png' });
} finally {
  await browser.close();
}
