/**
 * BgMacro — 지구본·세계 연결 배경 (1080x1920). 미국 주간(일요일) 달러·엔·원·유가·금 장면용.
 * 아래에서 떠오르는 지구(북태평양 중심, 정사영) — 대륙은 청록 점, 도시 불빛은 금색 점 · 서울/도쿄 ↔ 뉴욕/샌프란시스코 연결 호
 * · 지구를 도는 시세 기호 띠(USD/KRW · USD/JPY · DXY · WTI · XAU …) · 옅은 $ ¥ ₩ 글자와 원유 드럼통(질감)
 * + 톤 색 차트 선(오름 빨강 · 내림 파랑 · 옆걸음 금색). 숫자는 넣지 않는다(실제 값으로 오해되지 않게).
 * 상단 55%는 옅은 별만(큰 글자 자리). 프레임과 무관한 정적 그림 — public/bg/us_macro_<tone>.jpg 로 한 번 굽는다(BakeUSEntry.tsx).
 */
import React, { useId, useMemo } from "react";
import { AbsoluteFill } from "remotion";

export type Tone = "up" | "down" | "neutral";

const W = 1080;
const H = 1920;
const F = (n: number) => Math.round(n * 10) / 10;
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
const D2R = Math.PI / 180;
const MONO = "Consolas, 'DejaVu Sans Mono', monospace";
const KFONT = "Pretendard, 'Segoe UI', sans-serif";

function rng(seed: number) {
  let s = (Math.floor(seed) * 2654435761 + 1013904223) >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PAL: Record<Tone, { a: string; lt: string }> = {
  up: { a: "#FF4D4D", lt: "#FFC6BC" },
  down: { a: "#3D7BFF", lt: "#C6D8FF" },
  neutral: { a: "#F2C66D", lt: "#FFEBC4" },
};
const GOLD = "#FFC873";
const TEAL = "#3FD2C7";

// 지구: 화면 중심·반지름·시점(위도·경도)
const GX = 540;
const GY = 1780;
const R = 560;
const LAT0 = 25 * D2R;
const LON0 = -160 * D2R;

/** 정사영: 보이는 면이면 [x, y, 앞쪽정도(0~1)] */
function proj(lon: number, lat: number): [number, number, number] | null {
  const p = lat * D2R;
  const l = lon * D2R - LON0;
  const c = Math.sin(LAT0) * Math.sin(p) + Math.cos(LAT0) * Math.cos(p) * Math.cos(l);
  if (c <= 0) return null;
  const x = R * Math.cos(p) * Math.sin(l);
  const y = R * (Math.cos(LAT0) * Math.sin(p) - Math.sin(LAT0) * Math.cos(p) * Math.cos(l));
  return [GX + x, GY - y, c];
}

/* 대륙 윤곽(경도, 위도) — 보이는 북반구 위주로 단순화. 유라시아는 동쪽 끝(추코트카)을 180° 넘겨 적었다. */
type Poly = [number, number][];
const LAND: Poly[] = [
  // 북아메리카
  [[-168, 65.6], [-166, 68.9], [-163, 70.2], [-156.8, 71.3], [-152, 70.8], [-146, 70.2], [-141, 69.7], [-136, 69], [-129, 70], [-123, 69.4], [-117, 68.9], [-112, 67.8], [-108, 68.2], [-102, 67.8], [-97, 68.4], [-94, 69.3], [-92, 64], [-94.5, 59], [-92.5, 57], [-88, 56.5], [-84, 55.2], [-82.3, 52.5], [-79.5, 51.5], [-78.8, 54.5], [-77, 58.5], [-77.5, 61], [-74, 62.3], [-70, 61], [-67.5, 58.5], [-64.5, 60.3], [-61.5, 57], [-60, 55], [-57, 52.5], [-55.8, 51.7], [-58, 49], [-59.5, 47.6], [-65, 48.3], [-64.5, 46.2], [-61, 45.7], [-63.5, 44.6], [-65.9, 44.4], [-67, 44.9], [-70, 43.7], [-70.6, 41.6], [-72, 41.2], [-74, 40.5], [-74.2, 39.6], [-75.5, 38.8], [-76, 37], [-75.6, 35.3], [-77.5, 34.4], [-79, 33.3], [-81, 31.8], [-81.4, 30.5], [-80.1, 26.8], [-80.4, 25.2], [-81.2, 25.2], [-82.7, 27.8], [-82.8, 29.1], [-84.4, 30], [-86.5, 30.4], [-89, 30.3], [-89.6, 29.2], [-91, 29.3], [-94, 29.6], [-96.8, 28.2], [-97.4, 26], [-97.7, 24.1], [-97.3, 21.8], [-96.2, 19.2], [-94.5, 18.2], [-92.5, 18.5], [-91, 18.9], [-90.4, 20.8], [-88, 21.5], [-86.8, 21.2], [-87.5, 19], [-88.3, 17.5], [-88.2, 15.8], [-86, 15.9], [-84, 15.2], [-83.3, 13], [-83.7, 11], [-83, 9.5], [-81.5, 8.8], [-79.5, 9.6], [-77.4, 8.6], [-78, 7.4], [-80, 7.3], [-80.5, 8.2], [-82.8, 8.2], [-85.7, 10], [-85.7, 11.2], [-87.5, 13], [-89.3, 13.5], [-91.4, 14], [-93, 15.5], [-94.8, 16.2], [-96.5, 15.7], [-98.5, 16.2], [-101, 17.3], [-103.5, 18.3], [-105.4, 19.7], [-105.6, 21.7], [-106.4, 23.2], [-108, 24.8], [-109.4, 26.2], [-111, 27.9], [-112.8, 30.2], [-114.7, 31.7], [-114.2, 30], [-112.3, 27.2], [-110.3, 24.3], [-109.8, 22.9], [-111.3, 24.5], [-112.2, 26], [-114.2, 28.2], [-115.7, 30.2], [-117.1, 32.5], [-118.4, 33.8], [-120.6, 34.5], [-121.9, 36.5], [-122.5, 37.8], [-123.8, 39.8], [-124.3, 41.9], [-124.1, 44], [-124, 46.2], [-124.7, 48.4], [-125, 50], [-127.8, 50.9], [-130.3, 54.3], [-132.2, 56.3], [-134.2, 58.2], [-136.5, 58.3], [-139.7, 59.6], [-143, 60], [-146.5, 60.9], [-149.8, 61.2], [-151.6, 59.4], [-154.1, 57.6], [-156.8, 56.9], [-159.6, 55.8], [-162.3, 55], [-164.6, 54.5], [-162, 55.8], [-159, 58.4], [-161.8, 58.7], [-162, 60], [-164.7, 60.8], [-165.4, 62.6], [-164.1, 63.3], [-161, 64.1], [-161.3, 64.7], [-165.2, 64.5]],
  // 그린란드
  [[-73, 78.3], [-66, 80.6], [-58, 82.1], [-44, 83.2], [-30, 83.6], [-20, 82.2], [-17.5, 80], [-19, 77.5], [-18.5, 75], [-22, 72.5], [-22, 70.4], [-25, 68.8], [-31, 68], [-35, 66.3], [-39.5, 65.4], [-41, 63.7], [-43, 60.2], [-45.5, 60.7], [-48.5, 61.9], [-50.5, 64], [-52, 66], [-53.8, 67.8], [-51, 69.3], [-54.5, 70.8], [-56, 72.8], [-58, 75.2], [-62, 76.2], [-67, 76.5], [-71.5, 77.4]],
  // 캐나다 북극 섬들
  [[-80, 73.7], [-76, 72.6], [-71, 71], [-67.5, 69.2], [-64.5, 67.4], [-61.8, 66.2], [-64.2, 63.5], [-66, 62], [-68, 62.5], [-71.5, 63.6], [-74, 64.5], [-77.5, 64.3], [-78, 65.5], [-73.5, 66.8], [-73, 68.3], [-77, 69.5], [-80, 69.8], [-85, 70.2], [-89, 71.7], [-85.5, 73.2]],
  [[-90, 76.4], [-81, 76.2], [-78, 77.4], [-75, 79.5], [-66, 81.2], [-62, 82.4], [-72, 83], [-86, 82.3], [-94, 81], [-96, 78.5], [-91, 77]],
  [[-92, 74.5], [-80, 74.6], [-80.5, 76.3], [-90, 76.3], [-93, 75.5]],
  [[-119, 71.5], [-115, 73.3], [-106, 73], [-102, 71.5], [-101.5, 69.7], [-106, 69.2], [-113, 68.6], [-117.5, 69.5]],
  [[-125.5, 71.9], [-124, 74.3], [-117.5, 74.2], [-115.5, 72.8], [-120, 71.3]],
  [[-117, 75.5], [-104, 75.8], [-106, 77], [-114, 76.8]],
  [[-87, 64.2], [-80, 63.4], [-80.5, 64.8], [-86, 66.1]],
  [[-59.3, 47.6], [-56, 49.6], [-55.5, 51.6], [-53, 49.3], [-52.7, 47.5], [-55.5, 46.9]],
  [[-85, 21.9], [-80.5, 23.2], [-76.5, 21.2], [-74.1, 20.2], [-77.5, 19.8], [-81, 21.6]],
  [[-74.4, 19.8], [-71, 19.9], [-68.4, 18.6], [-71.5, 17.7], [-74.4, 18.4]],
  // 유라시아(북극해 → 유럽 → 아라비아 → 인도 → 동남아 → 중국 → 한반도 → 연해주 → 캄차카 → 추코트카)
  [[190.3, 66], [187.5, 67.4], [184, 68.3], [180, 68.9], [176, 69.9], [170, 70.1], [166, 69.6], [160.5, 70.2], [157, 71], [152, 70.9], [147, 72.2], [141, 72.8], [137, 71.5], [132, 71.5], [129, 72.5], [126.5, 73.5], [122, 73], [118, 73.6], [113, 73.7], [110, 74.5], [112.5, 76], [106, 77.2], [104, 77.7], [100, 76.5], [95, 76.1], [89, 75.3], [86.5, 74.6], [82, 73.6], [78, 72.3], [75, 72.8], [72.5, 72.5], [70, 73.4], [66.5, 69], [62, 69.8], [59, 68.6], [53.5, 68.8], [48, 67.8], [44, 68.5], [41, 66.5], [36, 68.9], [33, 69.4], [28.5, 71], [24, 71], [19, 70], [15, 68.8], [13.5, 67.5], [12, 65.3], [10.5, 64], [7, 62.6], [5, 61.5], [5, 59.3], [6.5, 58], [8, 58.2], [10.5, 59.2], [12.5, 56], [10.5, 57.7], [8.4, 57], [8.1, 55.5], [8.6, 53.9], [7, 53.5], [5, 53.3], [4, 51.9], [3, 51.3], [1.6, 50.9], [0.2, 49.7], [-1.9, 48.7], [-4.7, 48.4], [-4.3, 47.8], [-2.2, 47.1], [-1.2, 46], [-1.4, 44.3], [-1.8, 43.4], [-4, 43.4], [-8, 43.7], [-9.3, 43], [-8.8, 41], [-9.5, 38.8], [-8.8, 37], [-7.4, 37.2], [-6, 36.1], [-4.4, 36.7], [-2, 36.8], [-0.4, 38.4], [0.9, 41], [3.2, 41.9], [3, 43.2], [4.6, 43.4], [6.5, 43.1], [7.6, 43.8], [8.8, 44.4], [10.2, 43.9], [10.5, 42.9], [12.3, 41.7], [15.6, 40.1], [15.7, 38.2], [16.1, 38], [17.1, 39.3], [18.5, 40.1], [16.9, 41.1], [15.5, 41.9], [12.4, 44.5], [12.3, 45.4], [13.7, 45.6], [15.5, 43.9], [17, 43], [19.5, 41.8], [19.3, 40.5], [21.1, 38.3], [22.1, 36.5], [23.2, 36.4], [24, 38.2], [22.8, 40.5], [24, 40.8], [26, 40.8], [27, 38], [27.3, 37], [28.2, 36.7], [30.5, 36.2], [32.5, 36.1], [34.5, 36.7], [36, 36.3], [35.8, 35], [35.1, 33.1], [34.4, 31.4], [34.2, 31.3], [34.9, 29.5], [36.6, 26], [38.2, 24], [39.2, 21.5], [40.8, 19], [42.6, 16.4], [43.3, 13.3], [45, 12.8], [48.7, 14], [52.2, 15.7], [55.5, 17.3], [57.5, 18.9], [58.9, 21], [59.8, 22.4], [58.8, 25.5], [61.6, 25.2], [66.5, 25.4], [67.4, 24], [68.8, 23.2], [70.3, 21], [72.6, 21.3], [72.8, 19], [73.4, 16], [74.6, 13], [75.8, 11], [76.5, 8.7], [77.5, 8.1], [78.2, 8.9], [79.2, 10.3], [79.9, 11.9], [80.3, 15.5], [81.2, 16.4], [82.3, 17], [84.9, 19.3], [86.9, 20.8], [87.1, 21.6], [88.8, 21.6], [91.8, 22.3], [92.3, 20.7], [94.3, 17.5], [94.3, 16], [95.4, 15.7], [97.7, 16.5], [98.5, 12.5], [98.4, 9.5], [98.2, 8], [99.7, 6.5], [100.4, 5], [101.3, 2.9], [103.5, 1.3], [104.3, 1.4], [103.4, 3.8], [102.2, 6.2], [100.3, 8.4], [99.2, 10.2], [100.1, 13.4], [101.8, 12.7], [103.5, 10.6], [104.8, 9], [105.1, 8.6], [106.8, 10.4], [108.5, 11.3], [109.3, 11.9], [109.2, 13.4], [108.7, 15.4], [107.4, 16.8], [106.4, 18.2], [105.7, 19], [106.6, 20.4], [107.5, 21.5], [109.8, 21.5], [111.2, 21.5], [113.4, 22.2], [116, 22.8], [117.3, 23.6], [118.7, 24.6], [119.6, 25.7], [120.9, 28], [121.5, 29.2], [121.9, 30.8], [120.8, 32.6], [120.1, 34.3], [119.2, 34.8], [120.4, 36], [122.5, 37.4], [121.4, 37.8], [118.9, 37.4], [118.1, 38.3], [117.6, 39], [120.5, 40.2], [121.9, 40.8], [121.2, 38.8], [123.6, 39.8], [124.4, 39.9], [125.4, 38.6], [124.8, 38.1], [126.2, 37.7], [126.5, 36.1], [126.5, 34.9], [126.4, 34.4], [127.4, 34.7], [128.5, 34.9], [129.3, 35.3], [129.5, 36.1], [129.4, 37.1], [128.7, 38.2], [127.6, 39.2], [129.7, 40.8], [130.6, 42.3], [132.3, 43.2], [135.3, 43.9], [138.4, 46.7], [140.2, 48.4], [140.5, 50], [141, 53], [137.2, 54], [135.3, 54.7], [138.5, 56.7], [142.3, 59.2], [145.5, 59.4], [148.5, 59.3], [151.5, 59.1], [155, 59.5], [156.5, 57.9], [156, 55.5], [156.6, 51.2], [158.3, 52.9], [160, 54.1], [162.1, 55.9], [163.3, 56.1], [162.5, 57.8], [163.6, 59.9], [166.2, 60.4], [170.3, 60], [172.5, 61], [174.6, 61.9], [177.5, 62.6], [179.2, 62.4], [178.6, 64.6], [182, 65.4], [185, 64.6], [188.8, 65.6]],
  // 일본 · 홋카이도 · 사할린 · 대만 · 필리핀 · 보르네오 · 수마트라 · 스리랑카
  [[130.2, 31.2], [129.7, 33.1], [130.9, 33.9], [133.1, 35.5], [135.3, 35.6], [136.8, 37.3], [138.6, 37.8], [139.6, 38.6], [140, 39.9], [140.4, 41.3], [141.5, 41.3], [141.5, 40.2], [141.9, 39.2], [141, 37], [140.9, 35.7], [139.9, 34.9], [138.8, 34.6], [137.2, 34.6], [135.8, 33.5], [134.3, 33.4], [133, 32.7], [131.7, 31.5]],
  [[140.1, 41.5], [140, 42.5], [140.5, 43.3], [141.4, 43.4], [141.7, 45.4], [142.8, 44.6], [144.2, 44.1], [145.3, 44.3], [145.5, 43.3], [143.3, 42], [141.2, 41.8]],
  [[142, 46], [143.4, 46.6], [143.2, 49.2], [144.6, 49], [143, 51.5], [143.2, 53.3], [142.7, 54.3], [141.9, 53.4], [142.2, 51.5], [142, 49], [141.9, 47.6]],
  [[120.1, 23], [120.6, 24.5], [121.5, 25.3], [122, 25], [121.5, 23.5], [120.9, 22], [120.3, 22.5]],
  [[120.6, 18.5], [122.3, 18.4], [122.2, 16.3], [121.6, 15.8], [122.2, 14.1], [124.1, 13], [122.5, 13.4], [121, 13.8], [120.6, 14.6], [119.8, 16.2], [120.4, 17.5]],
  [[122, 7], [126.5, 7], [126.3, 9.5], [123.5, 8.5]],
  [[108.9, 1.3], [109.6, 2.1], [113.5, 3.2], [115.5, 5.4], [116.9, 7], [117.9, 6.1], [119.3, 5.2], [117.8, 1], [116.3, -1.5], [116, -3.8], [114.5, -4], [111, -3], [110.1, -1.6], [109, 0]],
  [[95.3, 5.6], [97.5, 5.2], [100.4, 2.2], [103.8, -0.5], [106, -3], [105.8, -5.8], [104.5, -5.9], [101, -2.5], [98.5, 1.7], [95.4, 4]],
  [[79.8, 9.8], [81.9, 7.4], [81.2, 6.2], [80, 6.1], [79.7, 8.2]],
  // 영국 · 아일랜드 · 아이슬란드 · 스발바르 · 노바야제믈랴 · 북극 섬
  [[-5.7, 50.1], [-3.5, 50.4], [0.3, 50.8], [1.4, 51.2], [1.7, 52.7], [0.2, 53.5], [-1.6, 55.6], [-1.8, 57.6], [-3.3, 58.6], [-5, 58.6], [-6.2, 56.6], [-4.9, 54.8], [-3, 53.4], [-4.6, 53.3], [-5.2, 51.8], [-3.2, 51.4]],
  [[-6, 52.2], [-6.1, 53.9], [-7.4, 55.3], [-10, 54.2], [-10.3, 51.9], [-9.5, 51.5], [-8, 51.8]],
  [[-24.3, 65.6], [-22, 66.4], [-16.5, 66.5], [-14.5, 65.8], [-13.6, 65], [-15, 64.3], [-18.7, 63.4], [-22.5, 63.8], [-24, 64.9]],
  [[11, 78.5], [13.5, 79.8], [17.5, 80.3], [22.5, 80.4], [27, 80], [21, 77.5], [17, 76.6], [14, 77.5]],
  [[52.5, 71.3], [57.5, 74.5], [61.5, 75.9], [68.5, 76.9], [66.5, 75.5], [57, 72], [55.5, 70.6]],
  [[96, 79], [98, 80.9], [104, 79.4], [100, 78.6]],
  [[136, 74.5], [140, 75.8], [147, 75.3], [142, 73.8]],
];

function inPoly(x: number, y: number, poly: Poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi) inside = !inside;
  }
  return inside;
}
const isLand = (lon: number, lat: number) => LAND.some((p) => inPoly(lon, lat, p) || inPoly(lon + 360, lat, p) || inPoly(lon - 360, lat, p));
// 도시 불빛이 모인 곳(금색 점 확률 높임)
const URBAN: [number, number, number, number][] = [[125, 34, 130, 38.6], [129, 31, 142, 41], [110, 22, 122.5, 40.5], [-90, 29, -70, 45], [-123, 32, -116, 39], [-100, 25, -94, 34], [-88, 39, -80, 44.5], [-124, 45, -121, 49]];

const CITY = { seoul: [127, 37.5], tokyo: [139.7, 35.7], ny: [-74, 40.7], sf: [-122.4, 37.8] } as const;

function makeScene(seed: number) {
  const r = rng(seed);
  // 대륙 점: 1.55° 격자, 가장자리로 갈수록 작고 옅게
  const buckets = ["", "", "", "", ""]; // 청록 3단계 + 금색 2단계
  const step = 1.55;
  for (let lat = -8; lat <= 84; lat += step) {
    const lonStep = step / Math.max(0.35, Math.cos(lat * D2R));
    for (let lon = -180; lon < 180; lon += lonStep) {
      const q = proj(lon, lat);
      if (!q || q[0] < -10 || q[0] > W + 10 || q[1] > H + 10) continue;
      if (!isLand(lon, lat)) continue;
      const c = q[2];
      const rad = 0.9 + 1.5 * c;
      const urban = URBAN.some(([a, b, cc, d]) => lon >= a && lon <= cc && lat >= b && lat <= d);
      let k = c > 0.66 ? 2 : c > 0.38 ? 1 : 0;
      if (urban && r() < 0.55) k = r() < 0.4 ? 4 : 3;
      else if (!urban && r() < 0.035) k = 3;
      buckets[k] += `M${F(q[0] - rad)} ${F(q[1])}a${F(rad)} ${F(rad)} 0 1 0 ${F(rad * 2)} 0a${F(rad)} ${F(rad)} 0 1 0 ${F(-rad * 2)} 0`;
    }
  }
  // 경위선
  let grat = "";
  for (let lon = -180; lon < 180; lon += 20) {
    let on = false;
    for (let lat = -30; lat <= 90; lat += 2) {
      const q = proj(lon, lat);
      if (!q) { on = false; continue; }
      grat += `${on ? "L" : "M"}${F(q[0])} ${F(q[1])}`;
      on = true;
    }
  }
  for (let lat = -15; lat <= 75; lat += 15) {
    let on = false;
    for (let lon = -180; lon <= 180; lon += 2) {
      const q = proj(lon, lat);
      if (!q) { on = false; continue; }
      grat += `${on ? "L" : "M"}${F(q[0])} ${F(q[1])}`;
      on = true;
    }
  }
  const stars = Array.from({ length: 80 }, () => ({ x: r() * W, y: lerp(30, 1180, r() ** 0.85), rr: lerp(0.6, 1.6, r() ** 2), op: lerp(0.08, 0.4, r() ** 2) }));
  const pt = (k: keyof typeof CITY) => { const q = proj(CITY[k][0], CITY[k][1])!; return [q[0], q[1]] as [number, number]; };
  return { buckets, grat, stars, seoul: pt("seoul"), tokyo: pt("tokyo"), ny: pt("ny"), sf: pt("sf") };
}

function makeChart(seed: number, tone: Tone) {
  const r = rng(seed * 13 + (tone === "up" ? 7 : tone === "down" ? 19 : 29));
  const N = 32;
  const x0 = -40, x1 = 900;
  const [ya, yb] = tone === "up" ? [1336, 1096] : tone === "down" ? [1100, 1330] : [1226, 1214];
  const pts: [number, number][] = [];
  let e = 0;
  for (let i = 0; i < N; i++) {
    const k = i / (N - 1);
    const base = lerp(ya, yb, tone === "neutral" ? k : Math.pow(k, 1.15));
    e = 0.55 * e + (r() - 0.5) * (tone === "neutral" ? 40 : 36);
    const osc = tone === "neutral" ? Math.sin(k * Math.PI * 3) * 20 : 0;
    pts.push([lerp(x0, x1, k), base + (i === 0 || i === N - 1 ? 0 : e + osc)]);
  }
  const s = Math.sign(yb - ya) || -1;
  if (tone !== "neutral") { pts[N - 3][1] = yb - s * 30; pts[N - 2][1] = yb - s * 36; }
  else { pts[N - 3][1] = yb + 16; pts[N - 2][1] = yb + 4; }
  pts[N - 1][1] = yb;
  const line = "M" + pts.map((p) => `${F(p[0])} ${F(p[1])}`).join("L");
  const minY = Math.min(...pts.map((p) => p[1]));
  return { line, fill: `${line}L${x1} ${minY + 360}L${x0} ${minY + 360}Z`, end: pts[N - 1], minY };
}

/** 원유 드럼통(선 그림) */
const Barrel: React.FC<{ x: number; y: number; s: number; op: number; col: string }> = ({ x, y, s, op, col }) => {
  const w = 60 * s, h = 84 * s, ry = 10 * s;
  return (
    <g opacity={op} fill="none" stroke={col} strokeWidth={2.2}>
      <ellipse cx={x} cy={y} rx={w / 2} ry={ry} />
      <path d={`M${x - w / 2} ${y}V${y + h}A${w / 2} ${ry} 0 0 0 ${x + w / 2} ${y + h}V${y}`} />
      <path d={`M${x - w / 2} ${y + h * 0.33}A${w / 2} ${ry} 0 0 0 ${x + w / 2} ${y + h * 0.33}M${x - w / 2} ${y + h * 0.66}A${w / 2} ${ry} 0 0 0 ${x + w / 2} ${y + h * 0.66}`} />
      <circle cx={x + w * 0.22} cy={y - ry * 0.1} r={3 * s} />
      <path d={`M${x} ${y + h * 0.42}c${-7 * s} ${9 * s} ${-7 * s} ${15 * s} 0 ${15 * s}c${7 * s} 0 ${7 * s} ${-6 * s} 0 ${-15 * s}z`} strokeWidth={1.8} />
    </g>
  );
};

export const BgMacro: React.FC<{ tone?: Tone; dim?: number; seed?: number }> = ({ tone = "neutral", dim = 0, seed = 9 }) => {
  const pal = PAL[tone] ?? PAL.neutral;
  const uid = "umc" + useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const id = (s: string) => `${uid}-${s}`;
  const u = (s: string) => `url(#${id(s)})`;
  const sc = useMemo(() => makeScene(seed), [seed]);
  const ch = useMemo(() => makeChart(seed, tone), [seed, tone]);
  const [ex, ey] = ch.end;
  const arc = (a: [number, number], b: [number, number], cy: number) => `M${F(a[0])} ${F(a[1])}Q${F((a[0] + b[0]) / 2)} ${cy} ${F(b[0])} ${F(b[1])}`;
  const arcs = [
    { d: arc(sc.seoul, sc.ny, 1010), w: 2.6, op: 0.85, col: GOLD },
    { d: arc(sc.tokyo, sc.ny, 1150), w: 1.8, op: 0.55, col: GOLD },
    { d: arc(sc.seoul, sc.sf, 1250), w: 1.6, op: 0.5, col: TEAL },
    { d: arc(sc.tokyo, sc.sf, 1390), w: 1.4, op: 0.42, col: TEAL },
  ];
  const ringR = R + 34;
  const ring = `M${GX - ringR} ${GY}A${ringR} ${ringR} 0 0 1 ${GX + ringR} ${GY}`;
  const TICK = "USD/KRW  ·  USD/JPY  ·  DXY  ·  EUR/USD  ·  WTI  ·  XAU/USD  ·  US10Y  ·  USD/CNH  ·  BRENT  ·  ";

  return (
    <AbsoluteFill style={{ background: "#01030A", overflow: "hidden" }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id={id("sky")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#010209" />
            <stop offset="0.4" stopColor="#030817" />
            <stop offset="0.6" stopColor="#061228" />
            <stop offset="0.68" stopColor="#0A1A36" />
            <stop offset="1" stopColor="#020510" />
          </linearGradient>
          <radialGradient id={id("globe")} gradientUnits="userSpaceOnUse" cx={GX - 150} cy={GY - 360} r={R * 1.25}>
            <stop offset="0" stopColor="#123150" />
            <stop offset="0.45" stopColor="#0A1C33" />
            <stop offset="0.85" stopColor="#050E1D" />
            <stop offset="1" stopColor="#030813" />
          </radialGradient>
          <radialGradient id={id("atmo")} gradientUnits="userSpaceOnUse" cx={GX} cy={GY} r={R + 90}>
            <stop offset={R / (R + 90) - 0.02} stopColor={TEAL} stopOpacity="0" />
            <stop offset={R / (R + 90)} stopColor={TEAL} stopOpacity="0.5" />
            <stop offset={(R + 26) / (R + 90)} stopColor="#2A8FB8" stopOpacity="0.16" />
            <stop offset="1" stopColor="#2A8FB8" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("rimIn")} gradientUnits="userSpaceOnUse" cx={GX} cy={GY} r={R}>
            <stop offset="0.86" stopColor={TEAL} stopOpacity="0" />
            <stop offset="1" stopColor={TEAL} stopOpacity="0.22" />
          </radialGradient>
          <radialGradient id={id("toneG")}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.22" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("warm")}>
            <stop offset="0" stopColor="#E9A04E" stopOpacity="0.16" />
            <stop offset="1" stopColor="#E9A04E" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("node")}>
            <stop offset="0" stopColor="#FFF1CF" stopOpacity="1" />
            <stop offset="0.3" stopColor={GOLD} stopOpacity="0.6" />
            <stop offset="1" stopColor={GOLD} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("chartF")} gradientUnits="userSpaceOnUse" x1="0" y1={F(ch.minY)} x2="0" y2={F(ch.minY + 340)}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.3" />
            <stop offset="0.5" stopColor={pal.a} stopOpacity="0.07" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("hfade")} gradientUnits="userSpaceOnUse" x1={-40} y1="0" x2={900} y2="0">
            <stop offset="0" stopColor="#fff" stopOpacity="0" />
            <stop offset="0.15" stopColor="#fff" stopOpacity="1" />
            <stop offset="0.78" stopColor="#fff" stopOpacity="1" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id={id("fillM")} maskUnits="userSpaceOnUse" x={-100} y={0} width={W + 200} height={H}>
            <rect x={-100} y={0} width={W + 200} height={H} fill={u("hfade")} />
          </mask>
          <radialGradient id={id("halo")}>
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.95" />
            <stop offset="0.22" stopColor={pal.a} stopOpacity="0.55" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("flare")} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0" />
            <stop offset="0.5" stopColor={pal.lt} stopOpacity="0.7" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("glyph")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={GOLD} stopOpacity="0.12" />
            <stop offset="1" stopColor={GOLD} stopOpacity="0.02" />
          </linearGradient>
          <clipPath id={id("globeC")}>
            <circle cx={GX} cy={GY} r={R} />
          </clipPath>
          <path id={id("ring")} d={ring} />
          <filter id={id("blurL")} filterUnits="userSpaceOnUse" x={-120} y={900} width={W + 240} height={620}>
            <feGaussianBlur stdDeviation="10" />
          </filter>
          <filter id={id("blurA")} filterUnits="userSpaceOnUse" x={-60} y={900} width={W + 120} height={800}>
            <feGaussianBlur stdDeviation="5" />
          </filter>
        </defs>

        {/* 우주 · 별 · 빛 */}
        <rect x={-20} y={-20} width={W + 40} height={H + 40} fill={u("sky")} />
        {sc.stars.map((s, i) => <circle key={i} cx={F(s.x)} cy={F(s.y)} r={s.rr} fill="#E8F0FF" opacity={s.op} />)}
        <ellipse cx={540} cy={1220} rx={760} ry={260} fill={u("toneG")} />
        <ellipse cx={880} cy={1300} rx={420} ry={220} fill={u("warm")} />

        {/* 옅은 통화 기호 · 드럼통(질감) */}
        <g fontFamily={KFONT} fontWeight={800} fill={u("glyph")} stroke={GOLD} strokeOpacity={0.14} strokeWidth={2}>
          <text x={34} y={1190} fontSize={230}>₩</text>
          <text x={820} y={1150} fontSize={250}>$</text>
          <text x={430} y={1060} fontSize={150} strokeOpacity={0.09}>¥</text>
        </g>
        <Barrel x={690} y={1010} s={1.1} op={0.16} col={GOLD} />
        <Barrel x={300} y={1110} s={0.72} op={0.12} col={TEAL} />

        {/* 지구 */}
        <circle cx={GX} cy={GY} r={R + 90} fill={u("atmo")} />
        <circle cx={GX} cy={GY} r={R} fill={u("globe")} />
        <g clipPath={u("globeC")}>
          <path d={sc.grat} fill="none" stroke={TEAL} strokeOpacity={0.09} strokeWidth={1.2} />
          <path d={sc.buckets[0]} fill={TEAL} opacity={0.26} />
          <path d={sc.buckets[1]} fill={TEAL} opacity={0.44} />
          <path d={sc.buckets[2]} fill={TEAL} opacity={0.6} />
          <path d={sc.buckets[3]} fill={GOLD} opacity={0.55} />
          <path d={sc.buckets[4]} fill="#FFE9BC" opacity={0.85} />
          <circle cx={GX} cy={GY} r={R} fill={u("rimIn")} />
        </g>
        <circle cx={GX} cy={GY} r={R} fill="none" stroke={TEAL} strokeOpacity={0.45} strokeWidth={1.6} />

        {/* 지구를 도는 시세 기호 띠 + 궤도선 */}
        <circle cx={GX} cy={GY} r={R + 78} fill="none" stroke={TEAL} strokeOpacity={0.14} strokeWidth={1.2} strokeDasharray="2 10" />
        <text fontFamily={MONO} fontSize={17} fontWeight={700} letterSpacing={2} fill={GOLD} opacity={0.34}>
          <textPath href={`#${id("ring")}`} startOffset="0">{TICK.repeat(4)}</textPath>
        </text>

        {/* 연결 호 + 도시 */}
        <g filter={u("blurA")}>
          {arcs.map((a, i) => <path key={i} d={a.d} fill="none" stroke={a.col} strokeOpacity={a.op * 0.7} strokeWidth={a.w * 3} />)}
        </g>
        {arcs.map((a, i) => <path key={i} d={a.d} fill="none" stroke={a.col} strokeOpacity={a.op} strokeWidth={a.w} strokeLinecap="round" strokeDasharray={i ? "10 7" : undefined} />)}
        {([["seoul", "서울"], ["tokyo", "도쿄"], ["ny", "뉴욕"], ["sf", ""]] as const).map(([k, lb]) => {
          const [x, y] = sc[k];
          return (
            <g key={k}>
              <circle cx={F(x)} cy={F(y)} r={22} fill={u("node")} />
              <circle cx={F(x)} cy={F(y)} r={9} fill="none" stroke={GOLD} strokeOpacity={0.7} strokeWidth={1.6} />
              <circle cx={F(x)} cy={F(y)} r={3.2} fill="#FFFFFF" />
              {lb ? <text x={F(x + (k === "ny" ? -16 : 16))} y={F(y - 16)} textAnchor={k === "ny" ? "end" : "start"} fontFamily={KFONT} fontWeight={800} fontSize={24} fill="#F4E6C8" opacity={0.7}>{lb}</text> : null}
            </g>
          );
        })}

        {/* 톤 차트 선 */}
        <path d={ch.fill} fill={u("chartF")} mask={u("fillM")} />
        <path d={ch.line} fill="none" stroke={pal.a} strokeOpacity={0.07} strokeWidth={38} strokeLinejoin="round" strokeLinecap="round" />
        <path d={ch.line} fill="none" stroke={pal.a} strokeOpacity={0.72} strokeWidth={12} strokeLinejoin="round" strokeLinecap="round" filter={u("blurL")} />
        <path d={ch.line} fill="none" stroke={pal.a} strokeWidth={4.4} strokeLinejoin="round" strokeLinecap="round" />
        <path d={ch.line} fill="none" stroke={pal.lt} strokeOpacity={0.9} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
        <rect x={F(ex - 260)} y={F(ey - 1.4)} width={520} height={2.8} fill={u("flare")} opacity={0.75} />
        <circle cx={F(ex)} cy={F(ey)} r={50} fill={u("halo")} />
        <circle cx={F(ex)} cy={F(ey)} r={17} fill="none" stroke={pal.a} strokeOpacity={0.5} strokeWidth={2} />
        <circle cx={F(ex)} cy={F(ey)} r={6.4} fill="#FFFFFF" />
      </svg>

      {/* 비네트 · 상단 암부 · 감광 */}
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <radialGradient id={id("vig")} gradientUnits="userSpaceOnUse" cx={540} cy={1320} r={1200}>
            <stop offset="0" stopColor="#000" stopOpacity="0" />
            <stop offset="0.55" stopColor="#000" stopOpacity="0" />
            <stop offset="0.82" stopColor="#000" stopOpacity="0.45" />
            <stop offset="1" stopColor="#000" stopOpacity="0.85" />
          </radialGradient>
          <linearGradient id={id("top")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" stopOpacity="0.5" />
            <stop offset="0.4" stopColor="#000" stopOpacity="0.12" />
            <stop offset="0.54" stopColor="#000" stopOpacity="0" />
            <stop offset="0.9" stopColor="#000" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.45" />
          </linearGradient>
        </defs>
        <rect width={W} height={H} fill={u("vig")} />
        <rect width={W} height={H} fill={u("top")} />
        {dim > 0 && <rect width={W} height={H} fill="#000" opacity={Math.min(1, dim)} />}
      </svg>
    </AbsoluteFill>
  );
};

export default BgMacro;
