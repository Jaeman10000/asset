"""BGM 샘플 생성 — 합성음이라 저작권 문제 없음. 24초, 48kHz 스테레오."""
import numpy as np, wave, sys

SR, DUR = 48000, 40.0
t = np.arange(int(SR * DUR)) / SR


def save(name, L, R=None):
    R = L if R is None else R
    x = np.stack([L, R], 1)
    x = x / max(1e-9, np.abs(x).max()) * 0.85
    with wave.open(name, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print("saved", name)


def adsr(dur, a=0.01, d=0.1, s=0.6, r=0.3):
    n = int(SR * dur); e = np.ones(n)
    na, nd, nr = int(SR * a), int(SR * d), int(SR * r)
    e[:na] = np.linspace(0, 1, na)
    e[na:na + nd] = np.linspace(1, s, nd)
    e[na + nd:n - nr] = s
    e[n - nr:] = np.linspace(s, 0, nr)
    return e


def place(buf, sig, at):
    i = int(SR * at); n = min(len(sig), len(buf) - i)
    if n > 0: buf[i:i + n] += sig[:n]


NOTE = lambda s: 440.0 * 2 ** ((s - 9) / 12)

# ── A. 뉴스룸 펄스 — 낮은 맥박 + 가벼운 하이햇, 브리핑 느낌
A = np.zeros_like(t)
bpm = 84; beat = 60 / bpm
for i in range(int(DUR / beat)):
    at = i * beat
    d = 0.28
    env = adsr(d, 0.002, 0.05, 0.25, 0.2)
    n = len(env); tt = np.arange(n) / SR
    f = 55 * np.exp(-tt * 6) + 42
    place(A, 0.55 * np.sin(2 * np.pi * f * tt) * env, at)       # 킥/맥박
    if i % 2 == 1:
        d2 = 0.06; e2 = adsr(d2, 0.001, 0.02, 0.1, 0.03)
        place(A, 0.08 * np.random.RandomState(i).randn(len(e2)) * e2, at + beat / 2)  # 하이햇
for i, s in enumerate([0, 7, 5, 7]):                            # 낮은 패드 진행
    f = NOTE(s - 12)
    seg = np.arange(int(SR * 6)) / SR
    pad = (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * f * 2 * seg)) * 0.12
    place(A, pad * adsr(6, 1.2, 1.0, 0.8, 1.5), i * 6)
save("bgm_A_newsroom.wav", A)

# ── B. 다크 아르페지오 — 긴장감, 경제사냥꾼 류
B = np.zeros_like(t)
arp = [0, 3, 7, 10, 12, 10, 7, 3]
step = 0.25
for i in range(int(DUR / step)):
    s = arp[i % len(arp)] + (0 if (i // 16) % 2 == 0 else -2)
    f = NOTE(s - 12)
    d = 0.5; e = adsr(d, 0.003, 0.08, 0.18, 0.35)
    tt = np.arange(len(e)) / SR
    saw = 2 * (tt * f - np.floor(0.5 + tt * f))
    place(B, 0.18 * saw * e, i * step)
for i, s in enumerate([0, -2, -4, -2]):
    f = NOTE(s - 24)
    seg = np.arange(int(SR * 6)) / SR
    place(B, 0.30 * np.sin(2 * np.pi * f * seg) * adsr(6, 0.8, 0.8, 0.9, 1.2), i * 6)
save("bgm_B_dark_arp.wav", B)

# ── C. 로파이 — 부드러운 일렉피아노 코드 + 느린 비트
C = np.zeros_like(t)
chords = [[0, 4, 7, 11], [-3, 2, 5, 9], [-5, 0, 4, 7], [-7, -2, 2, 5]]
for i, ch in enumerate(chords * 2):
    at = i * 3
    for s in ch:
        f = NOTE(s)
        d = 3.0; e = adsr(d, 0.02, 0.6, 0.35, 1.0)
        tt = np.arange(len(e)) / SR
        v = np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 2 * tt) + 0.12 * np.sin(2 * np.pi * f * 3 * tt)
        place(C, 0.10 * v * e * (1 + 0.02 * np.sin(2 * np.pi * 5 * tt)), at)
bpm = 72; beat = 60 / bpm
for i in range(int(DUR / beat)):
    at = i * beat
    e = adsr(0.22, 0.002, 0.05, 0.2, 0.15); tt = np.arange(len(e)) / SR
    place(C, 0.40 * np.sin(2 * np.pi * (48 * np.exp(-tt * 8) + 40) * tt) * e, at)
    if i % 2 == 1:
        e2 = adsr(0.12, 0.001, 0.04, 0.15, 0.07)
        place(C, 0.10 * np.random.RandomState(100 + i).randn(len(e2)) * e2, at)
C += 0.006 * np.random.RandomState(7).randn(len(C))             # 테이프 노이즈
save("bgm_C_lofi.wav", C)
