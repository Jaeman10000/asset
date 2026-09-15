export type Pt = { t: string; pct: number };
export type Minutes = {
  points?: Pt[]; open_pct?: number; high?: number; high_t?: string; high_pct?: number;
  low?: number; low_t?: string; low_pct?: number; close?: number; close_pct?: number;
  drop30?: { pct: number; from: string; to: string } | null; first_below_t?: string | null;
};
export type Index = {
  prev_close?: number | null; open?: number; high?: number; low?: number; close?: number; chg_pct?: number | null;
  range_pct?: number | null; minutes?: Minutes; streak?: number; program_mn?: number | null; program_eok?: number | null;
};
export type Move = {
  theme: string; y: number; t: number; delta: number; state: string; streak: number; avg5_strength: number;
  foreign: number; inst: number; ret: number; spread_names: string[]; moved_to?: string;
};
export type Scene = { id: string; min: number; tts: string; sub: string; audio?: string; audio_sec?: number; sec?: number; start?: number; frames?: number;
  /** 헌터 포맷: 문장별 단계 이름(문장 i번째 = steps[i]). 화면(v4/HunterV4.tsx)이 문장 경계(bounds)를 단계로 옮길 때 쓴다 */
  steps?: string[];
  /** tts.py 가 저장하는 문장 경계(문장당 1개, 장면 기준 초). cues 는 긴 문장을 쪼갠 자막 큐라 steps 와 개수가 다를 수 있다 */
  bounds?: { start: number; end: number; text: string }[] };
export type Props = {
  date: string; date_label: string; brand?: string; tagline?: string; edition?: string; qqq_points?: Pt[];
  kospi: Index; kosdaq: Index;
  investors: { state: string; src?: string | null; kospi: Record<string, number> | null; bars: { name: string; v: number | null }[]; title: string };
  us: { qqq_pct?: number | null; spy_pct?: number | null; qqq_points?: Pt[] | null; qqq_open_pct?: number | null; session_et?: string;
        events?: { src: string; kst: string; what: string }[]; y10?: number | null; y10_chg_bp?: number | null; wti?: number | null; wti_chg?: number | null; wti_date?: string };
  fx: { close: number; chg: number | null; note?: string } | null;
  moves: Move[]; s3_title: string;
  stocks: { name: string; pct: number; indiv: number; foreign: number; inst: number }[];
  news: { t?: string; text: string; band?: [string, string] }[];
  watch: { q: string; how: string; assist?: string }[];
  us_link?: { name: string; pct: number; close?: number; session?: string } | null; inv_streak?: Record<string, { streak: number; turned_after: number }>;
  next_label?: string; fx_said?: boolean; hook?: string;
  schedule: { d: string; t: string }[];
  caption: string; scenes: Scene[]; total_frames?: number; fps?: number; warnings: string[];
  /** 대본 형식: legacy(옛 s0~s6) · aplus(A+, v4 화면) · hunter(경제사냥꾼 슬롯 s0 s1 s2 s3a s3b s3c s4 s5 s6 — docs/HUNTER_FORMAT_DESIGN.md §6) */
  format?: "legacy" | "aplus" | "hunter";
  /** 헌터 포맷 화면 데이터(설계 §6.1 `hunter` 사전) — 모양은 v4/HunterV4.tsx 의 Hunter 타입 */
  hunter?: any;
};
