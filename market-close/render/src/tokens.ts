// SPEC §1-6 디자인 시스템 — 카드·영상 공통
export const C = {
  bg: "#161618",
  text: "#F2F2F0",
  sub: "#8E8E93",
  line: "#2A2A2E",
  up: "#FF5A4E",
  down: "#5B8CFF",
};
export const PAD = 96; // 좌우 여백 (1080 기준)
export const FONT = "Pretendard, 'Noto Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif";
export const SIZE = { head: 240, mid: 88, body: 64, small: 36, tiny: 30 };
export const FOOTER = "자동 생성 · AI 음성 · 운영자 규칙 · 추천 아님";

export const fontCss = `
@font-face{font-family:Pretendard;font-weight:400;src:url(FONT_REG) format('woff2');font-display:block}
@font-face{font-family:Pretendard;font-weight:600;src:url(FONT_SEMI) format('woff2');font-display:block}
@font-face{font-family:Pretendard;font-weight:800;src:url(FONT_XB) format('woff2');font-display:block}
@font-face{font-family:Pretendard;font-weight:900;src:url(FONT_BLK) format('woff2');font-display:block}
`;

export const colorOf = (v: number | null | undefined) => (v == null ? C.text : v > 0 ? C.up : v < 0 ? C.down : C.text);
export const fmtPct = (v: number | null | undefined, d = 2) =>
  v == null ? "—" : `${v > 0 ? "＋" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}%`;
export const fmtIdx = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtEok = (v: number | null | undefined, sign = false) => {
  if (v == null) return "—";
  const a = Math.abs(Math.round(v));
  const s = a >= 10000 ? (a % 10000 ? `${Math.floor(a / 10000)}조 ${(a % 10000).toLocaleString("ko-KR")}억` : `${a / 10000}조`) : `${a.toLocaleString("ko-KR")}억`;
  return (sign ? (v > 0 ? "＋" : v < 0 ? "−" : "") : "") + s;
};
export const hhmm = (t: string) => `${t.slice(0, 2)}:${t.slice(2)}`;
