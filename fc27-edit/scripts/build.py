"""FC27 TikTok edit: renders shots, overlays, sound design, and the two final versions.

Usage: python3 -I scripts/build.py [--only shots|final|audio] [--preview]
Run from fc27-edit/. Source clips are expected at raw/clip1..4.mp4.
"""
import json, math, os, subprocess, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, WORK, OUT, FONTS, AUD = (os.path.join(ROOT, d) for d in ("raw", "work", "out", "fonts", "audio"))
FPS, W, H = 30, 1080, 1920
BAR = 4 * 60 / 130                    # music: 130 BPM, 4/4
SQ, SQ_Y0, SQ_TOP = 820, 30, 380      # gameplay square: source crop size/top, position on canvas
PREVIEW = "--preview" in sys.argv

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stderr[-3000:]}")

# ---------------------------------------------------------------- timeline
# (name, clip, src_in, src_out, out_end, layout, keys)
#  layout: full = 9:16 crop following keys (centre x), sq = 1:1 crop (left x) over blurred bg,
#          zoom = fixed tight square, still = blurred freeze frame
K_G1 = [(0, 420), (5.0, 400), (6.8, 330), (7.6, 180), (8.2, 100), (8.6, 100)]
K_G2 = [(1.0, 560), (2.5, 520), (4.0, 420), (6.0, 300), (8.5, 230), (10.0, 200), (10.9, 180)]
K_G3 = [(3.2, 650), (6.0, 850), (9.0, 950), (10.4, 1000), (11.5, 1000)]
SHOTS = [
    ("intro", 1, 1.30, 3.15, 2 * BAR, "full", [(0, 1010)]),
    ("g1_build", 2, 0.00, 7.40, 7 * BAR - 1.6, "sq", K_G1),
    ("g1_shot", 2, 7.40, 8.50, 7 * BAR + 0.6, "sq", K_G1),
    ("g1_cel", 2, 11.55, 13.90, 9 * BAR, "full", [(11.55, 690), (12.0, 650), (13.0, 700), (13.9, 700)]),
    ("g2_build", 3, 1.00, 10.00, 15 * BAR - 4.24, "sq", K_G2),
    ("g2_shot", 3, 10.00, 10.90, 15 * BAR - 2.44, "sq", K_G2),
    ("g2_cel", 3, 14.45, 16.40, 15 * BAR, "full", [(14.45, 1230), (14.9, 1150), (15.5, 1160), (16.0, 1200), (16.4, 1250)]),
    ("g3_build", 4, 3.20, 10.50, 19 * BAR - 2.0, "sq", K_G3),
    ("g3_shot", 4, 10.50, 11.50, 19 * BAR, "sq", K_G3),
    ("fk_run", 1, 7.40, 9.60, 21 * BAR - 1.1, "full", [(0, 1010)]),
    ("fk_strike", 1, 9.60, 10.15, 21 * BAR, "full", [(0, 1010)]),
    ("fk_goal", 1, 10.20, 11.60, 21 * BAR + 2.0, "zoom", (140, 200, 640)),
    ("fk_cel", 1, 12.95, 16.30, 25 * BAR, "full", [(12.95, 1000), (13.4, 900), (13.9, 850), (14.4, 980), (14.9, 850), (15.4, 800), (16.3, 800)]),
    ("forfeit", 4, 17.70, 19.90, 25 * BAR + 2.2, "zoom", (510, 60, 900)),
    ("endcard", 1, 2.00, 2.00, 51.0, "still", None),
]

def timeline():
    t, out = 0.0, []
    for name, clip, a, b, end, layout, keys in SHOTS:
        f0, f1 = round(t * FPS), round(end * FPS)
        dur = (f1 - f0) / FPS
        out.append(dict(name=name, clip=clip, a=a, b=b, start=f0 / FPS, end=f1 / FPS, frames=f1 - f0,
                        speed=(b - a) / dur if b > a else 0, layout=layout, keys=keys))
        t = end
    return out

TL = timeline()
SHOT = {s["name"]: s for s in TL}
def at(name, src):
    """Output time at which source time `src` of shot `name` plays."""
    s = SHOT[name]
    return s["start"] + (src - s["a"]) / s["speed"]

GOALS = [at("g1_shot", 8.2), at("g2_shot", 10.7), at("g3_shot", 11.3), SHOT["fk_goal"]["start"]]
KICKS = [at("g1_shot", 7.6), at("g2_shot", 10.3), at("g3_shot", 10.8), at("fk_strike", 9.65)]
CUTS = [s["start"] for s in TL[1:]]
CELS = [SHOT[n]["start"] for n in ("g1_cel", "g2_cel", "fk_cel")]

# ---------------------------------------------------------------- shots
def ease_expr(keys, lo, hi):
    """Piecewise smoothstep over (t, v) keys, as an ffmpeg expression clipped to [lo, hi]."""
    if len(keys) == 1:
        return str(min(max(keys[0][1], lo), hi))
    e = str(keys[-1][1])
    for (t0, v0), (t1, v1) in reversed(list(zip(keys, keys[1:]))):
        f = f"((t-{t0})/{t1 - t0})"
        e = f"if(lt(t,{t1}),{v0}+({v1 - v0})*{f}*{f}*(3-2*{f}),{e})"
    e = f"if(lt(t,{keys[0][0]}),{keys[0][1]},{e})"
    return f"clip({e},{lo},{hi})"

def render_shot(i, s):
    src = os.path.join(RAW, f"clip{s['clip']}.mp4")
    dst = os.path.join(WORK, "shots", f"{i:02d}_{s['name']}.mp4")
    trim = f"trim=start={s['a']}:end={s['b']}"
    retime = f"setpts=(PTS-STARTPTS)/{s['speed']},fps={FPS}" if s["speed"] else ""
    pad = "tpad=stop_mode=clone:stop_duration=1"
    L, k = s["layout"], s["keys"]
    if L == "full":
        x = ease_expr([(t, c - 304) for t, c in k], 0, 1920 - 608)
        g = f"[0:v]{trim},crop=608:1080:x='{x}':y=0,{retime},scale={W}:{H}:flags=lanczos,{pad}[v]"
    elif L in ("sq", "zoom"):
        if L == "sq":
            crop = f"crop={SQ}:{SQ}:x='{ease_expr(k, 0, 1920 - SQ)}':y={SQ_Y0}"
        else:
            x0, y0, size = k
            crop = f"crop={size}:{size}:{x0}:{y0}"
        g = (f"[0:v]{trim},split[a][b];"
             f"[a]{crop},{retime},scale={W}:{W}:flags=lanczos[fg];"
             f"[b]{crop},{retime},scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
             f"boxblur=10:2,scale={W}:{H},eq=brightness=-0.16:saturation=0.75[bg];"
             f"[bg][fg]overlay=0:{SQ_TOP},{pad}[v]")
    else:  # still: blurred, darkened freeze frame for the end card
        g = (f"[0:v]trim=start={s['a']}:end={s['a'] + 0.05},setpts=PTS-STARTPTS,"
             f"scale=-2:{H},crop={W}:{H},boxblur=18:3,eq=brightness=-0.32:saturation=0.6,"
             f"fps={FPS},tpad=stop_mode=clone:stop_duration=10[v]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", g, "-map", "[v]",
         "-frames:v", str(s["frames"]), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "12", "-pix_fmt", "yuv420p", "-an", dst])
    return dst

def build_shots():
    os.makedirs(os.path.join(WORK, "shots"), exist_ok=True)
    files = []
    for i, s in enumerate(TL):
        files.append(render_shot(i, s))
        print(f"  shot {s['name']:<10} {s['start']:6.2f}-{s['end']:6.2f}s  speed {s['speed']:.2f}")
    lst = os.path.join(WORK, "shots.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in files)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", os.path.join(WORK, "video_raw.mp4")])

# ---------------------------------------------------------------- overlays (ASS)
ACC, WHITE = "&H003AFFD4&", "&H00FFFFFF&"   # accent: volt lime (#D4FF3A), BGR order
def ts(t):
    t = max(t, 0); cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"

def write_ass(path):
    styles = {
        # name: font, size, colour, bold, spacing, border, shadow
        "Title": ("Anton", 230, WHITE, 0, 4, 0, 0),
        "Sub": ("Bebas Neue", 70, WHITE, 0, 18, 4, 0),
        "Ar": ("Cairo Black", 86, WHITE, 0, 0, 5, 0),
        "Num": ("Anton", 110, ACC, 0, 2, 0, 0),
        "Chain": ("Bebas Neue", 76, WHITE, 0, 4, 0, 0),
        "Goal": ("Anton", 300, WHITE, 0, 12, 6, 0),
        "Name": ("Bebas Neue", 140, WHITE, 0, 6, 5, 0),
        "Small": ("Bebas Neue", 58, WHITE, 0, 10, 4, 0),
    }
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
            "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    for n, (font, size, col, bold, sp, bord, shad) in styles.items():
        head.append(f"Style: {n},{font},{size},{col},{col},&H64000000&,&H80000000&,{bold},0,0,0,"
                    f"100,100,{sp},0,1,{bord},{shad},5,0,0,0,1")
    head += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = []
    def add(t0, t1, style, text, layer=1):
        ev.append(f"Dialogue: {layer},{ts(t0)},{ts(t1)},{style},,0,0,0,,{text}")
    def slam(t0, t1, style, text, x, y, big=170, extra=""):
        add(t0, t1, style, f"{{\\pos({x},{y})\\fscx{big}\\fscy{big}\\alpha&HFF&"
                           f"\\t(0,140,\\fscx100\\fscy100\\alpha&H00&){extra}\\fad(0,220)}}{text}", 3)
    def rise(t0, t1, style, text, x, y, d=40, delay=0, extra=""):
        add(t0, t1, style, f"{{\\move({x},{y + d},{x},{y},{delay},{delay + 260})\\alpha&HFF&"
                           f"\\t({delay},{delay + 260},\\alpha&H00&){extra}\\fad(0,200)}}{text}")
    def chain(t0, t1, names, times, y=SQ_TOP + W + 70):
        parts = []
        for j, (nm, tt) in enumerate(zip(names, times)):
            sep = "  ›  " if j else ""
            col = ACC if j == len(names) - 1 else WHITE
            d = int((tt - t0) * 1000)
            parts.append(f"{{\\alpha&HFF&\\c{col}\\t({d},{d + 160},\\alpha&H00&)}}{sep}{nm}")
        add(t0, t1, "Chain", f"{{\\pos(540,{y})\\fad(0,200)}}" + "".join(parts))
    def header(t0, t1, num, label, y=SQ_TOP - 120):
        rise(t0, t1, "Num", num, 540, y - 58)
        rise(t0, t1, "Ar", label, 540, y + 50, delay=120, extra="\\fs68\\bord0")
    def lower_third(t0, t1, name, num, sub):
        x = 70
        add(t0 - 0.15, t1, "Small", "{\\an7\\p1\\pos(0,1180)\\bord0\\c&H000000&\\alpha&H30&\\blur40\\fad(150,250)}"
                                    "m 0 0 l 1080 0 l 1080 700 l 0 700{\\p0}", 1)
        add(t0, t1, "Name", f"{{\\an4\\move({x - 120},1380,{x},1380,0,300)\\alpha&HFF&\\t(0,300,\\alpha&H00&)"
                            f"\\fad(0,250)}}{name}  {{\\c{ACC}\\fnAnton\\fs130}}{num}", 2)
        add(t0, t1, "Small", f"{{\\an4\\move({x - 120},1478,{x},1478,80,380)\\alpha&HFF&"
                             f"\\t(80,380,\\alpha&H00&)\\fad(0,250)}}{sub}", 2)
        add(t0, t1, "Small", f"{{\\an4\\p1\\pos({x},1310)\\bord0\\c{ACC}\\fscx0\\t(0,350,\\fscx100)"
                             f"\\fad(0,250)}}m 0 0 l 420 0 l 420 10 l 0 10{{\\p0}}", 2)

    g1, g2, g3, gfk = GOALS
    # intro
    slam(0.10, SHOT["intro"]["end"] - 0.05, "Title", "FC 27", 540, 600)
    rise(0.35, SHOT["intro"]["end"] - 0.05, "Sub", "ALSHAMMARI · HIGHLIGHTS", 540, 735)
    add(0.75, SHOT["intro"]["end"] - 0.05, "Small", "{\\an7\\p1\\pos(130,1320)\\bord0\\c&H000000&\\alpha&H28&\\blur6\\fad(150,200)}"
                                              "m 0 0 l 820 0 l 820 280 l 0 280{\\p0}", 1)
    rise(0.80, SHOT["intro"]["end"] - 0.05, "Ar", "٤ أهداف.. خلك للأخير", 540, 1455, extra="\\bord0")
    # goal 1 — Nazareth
    s = SHOT["g1_build"]
    header(s["start"], g1, "01", "تيكي تاكا")
    chain(s["start"], g1 - 0.05, ["GUIJARRO", "PAJOR", "NAZARETH"],
          [s["start"], at("g1_build", 0.6), at("g1_build", 1.8)])
    slam(g1, SHOT["g1_shot"]["end"], "Goal", "GOAL", 540, 900)
    lower_third(SHOT["g1_cel"]["start"] + 0.15, SHOT["g1_cel"]["end"] - 0.1, "NAZARETH", "5", "GOAL 01 · TIKI-TAKA")
    # goal 2 — Pajor
    s = SHOT["g2_build"]
    header(s["start"], g2, "02", "تيكي تاكا")
    chain(s["start"], g2 - 0.05, ["YAMAL", "ADEYEMI", "PAJOR"],
          [s["start"], at("g2_build", 2.0), at("g2_build", 3.2)])
    slam(g2, SHOT["g2_shot"]["end"], "Goal", "GOAL", 540, 900)
    lower_third(SHOT["g2_cel"]["start"] + 0.15, SHOT["g2_cel"]["end"] - 0.1, "PAJOR", "17", "GOAL 02 · TIKI-TAKA")
    # goal 3 — Lamine Yamal
    s = SHOT["g3_build"]
    header(s["start"], g3, "03", "انطلاقة")
    chain(s["start"], SHOT["g3_shot"]["end"] - 0.05, ["PAJOR", "LAMINE YAMAL"], [s["start"], at("g3_build", 4.1)])
    slam(g3, SHOT["g3_shot"]["end"], "Goal", "GOAL", 540, 900)
    # free kick
    t0 = SHOT["fk_run"]["start"]
    rise(t0, gfk - 0.05, "Num", "04", 540, 260)
    slam(t0 + 0.1, gfk - 0.05, "Ar", "الفاول", 540, 400, big=150, extra="\\fs150")
    rise(t0 + 0.4, gfk - 0.05, "Small", "LAMINE YAMAL  ·  19.9 M  ·  xG 0.24", 540, 530)
    slam(gfk, SHOT["fk_goal"]["end"], "Goal", "GOLAZO", 540, 900, big=200,
         extra=f"\\c{ACC}\\fs250\\t(200,1800,\\fscx108\\fscy108)")
    lower_third(SHOT["fk_cel"]["start"] + 0.2, SHOT["fk_cel"]["end"] - 0.1, "LAMINE YAMAL", "9", "GOAL 04 · FREE KICK · 19.9 M")
    # forfeit punchline
    s = SHOT["forfeit"]
    rise(s["start"] + 0.3, s["end"], "Ar", "الخصم انسحب..", 540, SQ_TOP + W + 80)
    rise(s["start"] + 0.6, s["end"], "Small", "OPPONENT FORFEITED", 540, SQ_TOP + W + 185)
    # end card
    s = SHOT["endcard"]; e = s["end"]
    rise(s["start"] + 0.05, e, "Small", f"{{\\c{ACC}}}FULL TIME", 540, 640)
    rise(s["start"] + 0.15, e, "Chain", "BIRMINGHAM FC", 540, 760)
    slam(s["start"] + 0.30, e, "Title", "3 – 6", 540, 950, big=150, extra="\\fs260")
    rise(s["start"] + 0.55, e, "Chain", f"{{\\c{ACC}\\fs110}}ALSHAMMARI", 540, 1150)
    rise(s["start"] + 0.85, e, "Small", "NAZARETH · PAJOR · YAMAL ×2", 540, 1290, extra="\\alpha&H40&")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(head + ev) + "\n")

# ---------------------------------------------------------------- final video pass
def build_video():
    ass = os.path.join(WORK, "overlay.ass")
    write_ass(ass)
    flash = "+".join(f"{0.75 if T == GOALS[-1] else 0.5}*exp(-(t-{T:.3f})*9)*gte(t,{T:.3f})" for T in GOALS)
    def shake(freq, amp_scale):
        return "+".join(f"{(38 if T == GOALS[-1] else 22) * amp_scale}*sin((t-{T:.3f})*{freq})"
                        f"*exp(-(t-{T:.3f})*5)*gte(t,{T:.3f})" for T in GOALS)
    sw, sh = round(W * 1.05 / 2) * 2, round(H * 1.05 / 2) * 2
    mx, my = (sw - W) // 2, (sh - H) // 2
    vf = (f"scale={sw}:{sh},crop={W}:{H}:x='clip({mx}+{shake(57, 1)},0,{2 * mx})':y='clip({my}+{shake(43, 0.8)},0,{2 * my})',"
          f"eq=contrast=1.10:saturation=0.90:gamma=0.97,"
          f"colorbalance=rs=-0.04:bs=0.05:rh=0.05:bh=-0.04,"
          f"vignette=angle=0.5,noise=alls=4:allf=t,"
          f"eq=brightness='{flash}':eval=frame,"
          f"ass={ass}:fontsdir={FONTS},format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(WORK, "video_raw.mp4"), "-vf", vf,
         "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast" if PREVIEW else "slow", "-crf", "19", "-maxrate", "18M", "-bufsize", "36M",
         "-profile:v", "high", "-an", os.path.join(WORK, "video_final.mp4")])

# ---------------------------------------------------------------- audio
SR = 44100
rng = np.random.default_rng(9)
def load(name):
    with wave.open(os.path.join(AUD, name)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels()).T
def bandnoise(n, lo, hi):
    X = np.fft.rfft(rng.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n)
def smooth_rand(n, rate):
    k = max(2, int(n / SR * rate)); pts = rng.random(k + 1)
    return np.interp(np.linspace(0, k, n), np.arange(k + 1), pts)
def crowd_bed(dur):
    n = int(dur * SR); out = np.zeros(n)
    for c in np.geomspace(250, 2800, 14):          # many 'voices' = band-limited noise with slow swells
        out += bandnoise(n, c * 0.8, c * 1.25) * (0.4 + smooth_rand(n, rng.uniform(1.5, 4)))
    return out / np.max(np.abs(out))
def thump():
    t = np.arange(int(0.18 * SR)) / SR
    body = np.sin(2 * np.pi * np.cumsum(70 + 120 * np.exp(-t * 60)) / SR) * np.exp(-t * 30)
    return body + bandnoise(len(t), 800, 4000) * np.exp(-t * 80) * 0.6
def net_swish():
    t = np.arange(int(0.45 * SR)) / SR
    return bandnoise(len(t), 1500, 7000) * np.sin(np.pi * t / t[-1]) ** 0.5 * np.exp(-t * 4)

def build_audio(dur):
    n = int(dur * SR)
    def track(): return np.zeros((2, n))
    def put(tr, x, t, g=1.0):
        x = np.atleast_2d(x)
        if x.shape[0] == 1: x = np.vstack([x, x])
        i = int(t * SR); m = min(x.shape[1], n - i)
        if m > 0: tr[:, i:i + m] += x[:, :m] * g
    S = {k: load(f"sfx/{k}.wav") for k in ("whoosh_up", "whoosh_down", "impact_boom", "riser_2s",
                                            "heartbeat", "crowd_roar", "tape_stop", "glitch", "reverse_cymbal")}
    sfx = track()
    for t in CUTS:
        if t in CELS: continue
        put(sfx, S["whoosh_up"], t - 0.30, 0.35)
    for t in CELS: put(sfx, S["whoosh_down"], t - 0.15, 0.30)
    for t in KICKS: put(sfx, thump(), t, 0.55)
    for t in GOALS:
        big = t == GOALS[-1]
        put(sfx, S["impact_boom"], t, 0.75 if big else 0.55)
        put(sfx, net_swish(), t, 0.35)
        put(sfx, S["reverse_cymbal"], t - 1.2, 0.20)
    put(sfx, S["tape_stop"], SHOT["forfeit"]["start"] - 0.05, 0.35)
    put(sfx, S["glitch"], SHOT["endcard"]["start"], 0.25)
    put(sfx, S["impact_boom"], SHOT["endcard"]["start"] + 0.30, 0.45)

    crowd = track(); bed = crowd_bed(dur)
    put(crowd, np.vstack([bed, np.roll(bed, 2000)]), 0, 1.0)
    roar = track()
    for t in GOALS:
        swell = crowd_bed(4.0) * np.minimum(1, np.arange(4 * SR) / (0.25 * SR)) * np.exp(-np.arange(4 * SR) / SR * 0.7)
        put(roar, np.vstack([swell, np.roll(swell, 1500)]), t, 1.6 if t == GOALS[-1] else 1.2)

    fk0, fk1 = SHOT["fk_run"]["start"], GOALS[-1]
    tension = track()
    for k in range(2): put(tension, S["heartbeat"], fk0 + k * 1.85, 0.8)
    put(tension, S["riser_2s"], fk1 - 2.0, 0.35)
    duck = np.ones(n); i0, i1 = int(fk0 * SR), int(fk1 * SR)
    duck[i0:i1] = np.linspace(1, 0.35, i1 - i0)       # crowd goes quiet before the free kick

    def finish(x, target_peak=0.84, drive=1.2):
        fade = int(1.2 * SR); x[:, -fade:] *= np.linspace(1, 0, fade)
        x = x / np.max(np.abs(x))
        x = np.tanh(x * drive) / np.tanh(drive)
        return x / np.max(np.abs(x)) * target_peak

    music = load("music_phonk_130bpm.wav")[:, :n]
    music = np.pad(music, ((0, 0), (0, n - music.shape[1])))
    mix_music = music * 0.80 + sfx * 0.9 + crowd * duck * 0.06 + roar * 0.10
    mix_clean = sfx * 1.0 + crowd * duck * 0.22 + roar * 0.30 + tension * 1.0
    return finish(mix_music), finish(mix_clean, drive=3.0)

def save_wav(path, x):
    d = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(d.tobytes())

def mux(audio, name):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(WORK, "video_final.mp4"), "-i", audio,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "44100",
         "-shortest", "-movflags", "+faststart", dst])
    return dst

if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    os.makedirs(WORK, exist_ok=True)
    json.dump(dict(goals=GOALS, kicks=KICKS, shots=TL), open(os.path.join(WORK, "timeline.json"), "w"), indent=1)
    if only in (None, "shots"):
        print("rendering shots…"); build_shots()
    if only in (None, "final"):
        print("final video pass…"); build_video()
    if only in (None, "final", "audio"):
        dur = TL[-1]["end"]
        m, c = build_audio(dur)
        save_wav(os.path.join(WORK, "mix_music.wav"), m); save_wav(os.path.join(WORK, "mix_clean.wav"), c)
        print(mux(os.path.join(WORK, "mix_music.wav"), "FC27_tiktok_music.mp4"))
        print(mux(os.path.join(WORK, "mix_clean.wav"), "FC27_tiktok_no_music.mp4"))
