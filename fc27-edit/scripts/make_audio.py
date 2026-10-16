"""Original (copyright-free) phonk-style beat + SFX pack for the FC27 TikTok edit.
All sounds are synthesized from scratch with numpy, so there are no rights issues."""
import numpy as np, wave, os, sys

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else "audio"
rng = np.random.default_rng(27)

def t(d): return np.arange(int(d * SR)) / SR
def env(n, a=0.002, r=None, curve=6.0):
    x = np.linspace(0, 1, n)
    e = np.exp(-curve * x) if r is None else np.clip(1 - x / r, 0, 1) ** 2
    att = max(1, int(a * SR)); e[:att] *= np.linspace(0, 1, att)
    return e
def sat(x, k=2.0): return np.tanh(k * x) / np.tanh(k)
def fft_conv(x, ir):
    n = len(x) + len(ir) - 1; N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:n]
def reverb(x, dur=1.6, mix=0.25):
    ir = rng.standard_normal(int(dur * SR)) * np.exp(-5 * t(dur) / dur)
    ir[0] = 0
    w = fft_conv(x, ir)[: len(x)]
    w /= np.max(np.abs(w)) + 1e-9
    return x * (1 - mix) + w * mix * np.max(np.abs(x))
def lowpass(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / cutoff) ** 8), len(x))
def highpass(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (cutoff / np.maximum(f, 1)) ** 8), len(x))
def norm(x, peak=0.89): return x / (np.max(np.abs(x)) + 1e-9) * peak
def save(name, x):
    x = np.atleast_2d(x)
    if x.shape[0] == 1: x = np.vstack([x, x])
    d = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(d.tobytes())

# ---------- instruments ----------
def kick(d=0.45):
    tt = t(d); f = 45 + 160 * np.exp(-tt * 28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), curve=7)
    click = rng.standard_normal(len(tt)) * np.exp(-tt * 300) * 0.3
    return sat(s + click, 3)
def snare(d=0.3):
    tt = t(d)
    body = np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 25)
    nz = highpass(rng.standard_normal(len(tt)), 1500) * np.exp(-tt * 14)
    return sat(body * 0.6 + nz * 0.9, 2)
def clap(d=0.3):
    tt = t(d); nz = highpass(rng.standard_normal(len(tt)), 1000)
    e = sum(np.exp(-np.maximum(tt - o, 0) * 60) * (tt >= o) for o in (0, 0.01, 0.02))
    return nz * e * np.exp(-tt * 9)
def hat(d=0.06, open_=False):
    tt = t(0.25 if open_ else d)
    return highpass(rng.standard_normal(len(tt)), 7000) * np.exp(-tt * (12 if open_ else 80))
def cowbell(freq, d=0.22):
    tt = t(d)
    s = sum(np.sign(np.sin(2 * np.pi * freq * m * tt)) for m in (1, 1.48))
    return lowpass(s * np.exp(-tt * 11), 4500) * 0.5
def bass808(freq, d):
    tt = t(d); f = freq * (1 + 0.6 * np.exp(-tt * 40))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return sat(s * env(len(tt), a=0.003, curve=1.6), 2.5)
def pad(freqs, d):
    tt = t(d); s = np.zeros(len(tt))
    for fr in freqs:
        for det in (-0.3, 0, 0.3):
            ph = 2 * np.pi * (fr + det) * tt
            s += 2 * (ph / (2 * np.pi) % 1) - 1
    s = lowpass(s, 1400)
    e = np.minimum(1, tt / 0.4) * np.minimum(1, (d - tt) / 0.4)
    return s * e

# ---------- song ----------
BPM = 130; BEAT = 60 / BPM; BAR = 4 * BEAT; STEP = BEAT / 4
BARS = 26
song = np.zeros((2, int((BARS * BAR + 3) * SR)))
def place(x, at, gain=1.0, pan=0.0):
    i = int(at * SR); x = x[: song.shape[1] - i]
    song[0, i:i + len(x)] += x * gain * (1 - max(pan, 0))
    song[1, i:i + len(x)] += x * gain * (1 + min(pan, 0))

# A minor phonk: cowbell riff (16th grid, None = rest)
N = lambda m: 440 * 2 ** ((m - 69) / 12)
riff = [69, None, 72, None, 69, 76, None, 74, None, 72, 69, None, 67, None, 69, None]
riff2 = [69, None, 72, None, 74, 76, None, 79, None, 76, 74, None, 72, None, 71, None]
bassline = [(45, 0, 1.5), (45, 1.75, 0.5), (48, 2.5, 0.75), (43, 3.25, 0.75)]
chords = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 56, 59]]  # Am F G E

# sections (bar ranges): intro 0-4, dropA 4-12, break 12-14, dropB 14-24, outro 24-26
for b in range(BARS):
    t0 = b * BAR
    intro, drop_a, brk, drop_b, outro = b < 4, 4 <= b < 12, 12 <= b < 14, 14 <= b < 24, b >= 24
    ch = [N(m) for m in chords[b % 4]]
    if intro or brk or outro:
        place(pad(ch, BAR), t0, 0.10)
    if intro and b >= 2:                           # filtered riff teaser
        for s, m in enumerate(riff):
            if m: place(lowpass(cowbell(N(m)), 900), t0 + s * STEP, 0.35)
    if brk:                                        # heartbeat for the free-kick slow-mo
        for beat in range(4):
            place(lowpass(kick(0.3), 200), t0 + beat * BEAT, 0.5)
            place(lowpass(kick(0.3), 200), t0 + beat * BEAT + 0.16, 0.3)
    if drop_a or drop_b:
        r = riff2 if (drop_b and b % 2) else riff
        for s, m in enumerate(r):
            if m: place(cowbell(N(m)), t0 + s * STEP, 0.42, pan=0.15 if s % 2 else -0.15)
        for k in (0, 1.5, 2.75) if drop_b else (0, 2.5):
            place(kick(), t0 + k * BEAT, 0.9)
        for sn in (1, 3):
            place(snare(), t0 + sn * BEAT, 0.5); place(clap(), t0 + sn * BEAT, 0.35)
        for s in range(16):
            roll = drop_b and b % 4 == 3 and s >= 12
            if roll:
                for sub in range(3): place(hat(), t0 + s * STEP + sub * STEP / 3, 0.22)
            elif s % 2 == 0 or drop_b:
                place(hat(), t0 + s * STEP, 0.2 if s % 4 == 0 else 0.12)
        for m, st, ln in bassline:
            place(bass808(N(m), ln * BEAT), t0 + st * BEAT, 0.75)
    if outro and b == 24:
        place(bass808(N(45), BAR * 1.5), t0, 0.8)
        place(kick(), t0, 1.0)

# riser into each drop + impact on the downbeat
def riser(d):
    tt = t(d); f = 200 * 2 ** (tt / d * 4)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + highpass(rng.standard_normal(len(tt)), 3000) * 0.5
    return s * (tt / d) ** 2
def impact(d=2.5):
    tt = t(d); f = 30 + 90 * np.exp(-tt * 6)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 1.6)
    crack = lowpass(rng.standard_normal(len(tt)), 5000) * np.exp(-tt * 9) * 0.6
    return reverb(sat(boom + crack, 2), 2.0, 0.35)
for bar in (4, 14):
    place(riser(2 * BAR), (bar - 2) * BAR, 0.35)
    place(impact(), bar * BAR, 0.6)

mix = song.copy()
mix[0] = reverb(mix[0], 1.2, 0.12); mix[1] = reverb(mix[1], 1.25, 0.12)
mix = sat(norm(mix, 1.0) * 1.3, 1.6)            # glue / loudness
fade = int(2.5 * SR); mix[:, -fade:] *= np.linspace(1, 0, fade)
os.makedirs(OUT, exist_ok=True)
save("music_phonk_130bpm.wav", norm(mix, 0.95))

# ---------- SFX pack ----------
sfx = os.path.join(OUT, "sfx"); os.makedirs(sfx, exist_ok=True)
def ssave(n, x): save(os.path.join("sfx", n), norm(x))
def whoosh(d=0.6, up=True):
    tt = t(d); nz = rng.standard_normal(len(tt)); out = np.zeros(len(tt))
    seg = 2048
    for i in range(0, len(tt), seg):
        p = i / len(tt); c = 400 + 6000 * (p if up else 1 - p)
        out[i:i + seg] = highpass(lowpass(nz[i:i + seg], c * 1.5), c * 0.4)[: len(out[i:i + seg])]
    return out * np.sin(np.pi * tt / d) ** 2
ssave("whoosh_up.wav", whoosh(0.55, True))
ssave("whoosh_down.wav", whoosh(0.55, False))
ssave("impact_boom.wav", impact())
ssave("riser_2s.wav", riser(2.0))
ssave("bass_drop.wav", bass808(N(33), 2.0))
tt = t(1.0); ssave("tape_stop.wav", sat(np.sin(2 * np.pi * np.cumsum(220 * (1 - tt) ** 2) / SR) * (1 - tt), 2))
tt = t(0.12); ssave("camera_shutter.wav", highpass(rng.standard_normal(len(tt)), 2500) * (np.exp(-tt * 70) + 0.6 * np.exp(-np.maximum(tt - 0.05, 0) * 90) * (tt > 0.05)))
g = np.concatenate([np.sign(np.sin(2 * np.pi * rng.uniform(200, 2000) * t(0.025))) * 0.5 for _ in range(10)])
ssave("glitch.wav", g)
hb = np.zeros(int(2 * SR))
for o in (0, 0.18, 0.9, 1.08):
    k = lowpass(kick(0.3), 180); i = int(o * SR); hb[i:i + len(k)] += k * (1 if o in (0, 0.9) else 0.6)
ssave("heartbeat.wav", hb)
tt = t(3.0)
crowd = lowpass(highpass(rng.standard_normal(len(tt)), 300), 3000) * np.minimum(1, tt / 0.3) * np.exp(-np.maximum(tt - 1.2, 0) * 1.2)
ssave("crowd_roar.wav", reverb(crowd, 1.5, 0.4))
tt = t(1.2); rev = (highpass(rng.standard_normal(len(tt)), 5000) * np.exp(-tt * 3))[::-1]
ssave("reverse_cymbal.wav", rev)
print("bar length (s):", BAR, " drops at:", 4 * BAR, 14 * BAR, " break:", 12 * BAR, "-", 14 * BAR)
