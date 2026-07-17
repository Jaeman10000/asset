// 청록 심장 앱 아이콘 소스 PNG(1024)를 puppeteer로 렌더.
// 이후 `npx tauri icon <out>` 으로 전체 플랫폼 아이콘을 생성한다.
import puppeteer from 'puppeteer-core';
import { existsSync } from 'node:fs';

const CHROME = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].find(existsSync);

const out = process.argv[2] ?? './icon-source.png';
const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <radialGradient id="bg" cx="50%" cy="42%" r="70%">
      <stop offset="0%" stop-color="#0b1217"/>
      <stop offset="100%" stop-color="#05080b"/>
    </radialGradient>
    <radialGradient id="heart" cx="50%" cy="40%" r="70%">
      <stop offset="0%" stop-color="#7bffe6"/>
      <stop offset="55%" stop-color="#2be6c8"/>
      <stop offset="100%" stop-color="#1a9e8c"/>
    </radialGradient>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="26" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="1024" height="1024" rx="220" fill="url(#bg)"/>
  <g filter="url(#glow)" transform="translate(512,540) scale(20)">
    <path transform="translate(-12,-11)"
      d="M12 21s-7.5-4.9-10.2-9.3C0 8.9 1.2 5.5 4.2 4.6 6.4 3.9 8.6 4.9 10 6.8c0.6 0.8 1.4 1.9 2 1.9s1.4-1.1 2-1.9c1.4-1.9 3.6-2.9 5.8-2.2 3 0.9 4.2 4.3 2.4 7.1C19.5 16.1 12 21 12 21z"
      fill="url(#heart)"/>
  </g>
</svg>`;

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--force-device-scale-factor=1'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1024, height: 1024, deviceScaleFactor: 1 });
  await page.setContent(
    `<style>html,body{margin:0;padding:0}</style>${svg}`,
    { waitUntil: 'networkidle0' },
  );
  await page.screenshot({ path: out, omitBackground: true, clip: { x: 0, y: 0, width: 1024, height: 1024 } });
  console.log('아이콘 소스 생성:', out);
} finally {
  await browser.close();
}
