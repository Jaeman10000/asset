// capture-stage.mjs — GUIDE.md 통합 단계를 headless 브라우저로 캡처해 검증한다.
// 사용: node scripts/capture-stage.mjs <outDir> [stage ...]
// 예:  node scripts/capture-stage.mjs ./shots 1 2 3 4 5 6 7
//
// puppeteer-core + 시스템 Chrome/Edge (브라우저 다운로드 없음).
// headless는 SwiftShader(소프트웨어 GL)라 느리지만 시각 검증에는 충분하다.

import puppeteer from 'puppeteer-core';
import { existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

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

const outDir = resolve(process.argv[2] ?? './shots');
const stages = process.argv.slice(3).length ? process.argv.slice(3) : ['1'];
mkdirSync(outDir, { recursive: true });

// ANGLE=d3d11 환경변수를 주면 하드웨어 GPU로 시도 (실측 FPS용),
// 기본은 SwiftShader (소프트웨어, 시각 검증용)
const angle = process.env.ANGLE ?? 'swiftshader';
const waitMs = Number(process.env.WAIT_MS ?? 9_000);

const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--enable-unsafe-swiftshader',
    '--use-gl=angle',
    `--use-angle=${angle}`,
    '--window-size=1280,720',
  ],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });

  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      console.log(`[console.${type}] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => console.log(`[pageerror] ${err.message}`));

  for (const stage of stages) {
    const url = `http://localhost:5173/?stage=${stage}`;
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60_000 });
    // 소프트웨어 GL에서 트랜스미션/환경맵이 자리잡을 때까지 프레임 누적 대기
    await page.waitForSelector('.scene-layer canvas', { timeout: 30_000 });
    await new Promise((r) => setTimeout(r, waitMs));

    const file = `${outDir}\\stage-${stage}.png`;
    await page.screenshot({ path: file });

    const info = await page.evaluate(() => ({
      fps: document.querySelector('.fps-meter')?.textContent ?? null,
      qualityLevel: window.__qualityLevel ?? null,
      badge: document.querySelector('.stage-badge')?.textContent ?? null,
      canvasSize: (() => {
        const c = document.querySelector('.scene-layer canvas');
        return c ? [c.width, c.height] : null;
      })(),
      cards: document.querySelectorAll('.glass-card').length,
      lifeVar: getComputedStyle(document.documentElement).getPropertyValue('--life').trim(),
    }));
    console.log(`stage ${stage}: ${JSON.stringify(info)} -> ${file}`);
  }
} finally {
  await browser.close();
}
