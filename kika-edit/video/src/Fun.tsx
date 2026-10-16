// Version 2: same cut and commentary as KikaMessi, restyled to be punchy and colourful
// rather than cinematic. All effects are HTML/SVG so they render with the OffthreadVideo fallback.
import { Audio, Video } from "@remotion/media";
import React from "react";
import {
  AbsoluteFill,
  Composition,
  Easing,
  Img,
  interpolate,
  random,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  A_RATE,
  A_SRC0,
  Cam,
  clamp,
  COND,
  END,
  FPS,
  H,
  KIKA_FILE_OFFSET,
  KIKA_GOAL,
  KIKA_SRC_SIZE,
  kikaCam,
  MESSI_SRC_SIZE,
  messiCam,
  panelStyle,
  S_KIKA_RATE,
  S_KIKA_SRC0,
  S_MESSI_RATE,
  S_MESSI_SRC0,
  SPLIT_GOAL,
  SPLIT_IN,
  W,
} from "./Composition";
import { KIKA_TRACK } from "./data/kikaTrack";

const VOLT = "#D7FF2F";
const PINK = "#FF2E88";
const BARCA = "#A50044";
const INK = "#0B0B0F";
const POP = "saturate(1.32) contrast(1.12) brightness(1.04)";

// Kika's two cut-backs (direction changes in the tracked path), in source seconds.
const SKILLS = [3.6, 6.9];
const aFrame = (src: number) => Math.round(((src - A_SRC0) / A_RATE) * FPS);
// Goal mouth in the source frame (centre of the net), for the particle burst.
const GOAL_SRC = { x: 320, y: 370 };

const sp = (f: number, start: number, damping = 11, mass = 0.6) =>
  spring({ frame: f - start, fps: FPS, config: { damping, mass, stiffness: 170 } });

// Source pixel -> panel pixel for a given camera.
const toScreen = (cam: Cam, outW: number, outH: number, x: number, y: number) => {
  const k = outW / cam.cw;
  const ch = outH / k;
  return { x: (x - (cam.cx - cam.cw / 2)) * k, y: (y - (cam.cy - ch / 2)) * k, k };
};

// ---- RGB split (SVG filter, driven per frame) ------------------------------------
const RgbFilter: React.FC<{ id: string; amount: number }> = ({ id, amount }) => (
  <svg width={0} height={0} style={{ position: "absolute" }}>
    <filter id={id} x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
      <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
      <feOffset in="r" dx={amount} dy={0} result="r2" />
      <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
      <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
      <feOffset in="b" dx={-amount} dy={amount * 0.3} result="b2" />
      <feBlend in="r2" in2="g" mode="screen" result="rg" />
      <feBlend in="rg" in2="b2" mode="screen" />
    </filter>
  </svg>
);

const hit = (f: number, at: number, len = 14) =>
  f >= at ? Math.exp(-(f - at) / (len / 3)) * (f - at < len ? 1 : 0) : 0;

// ---- Kika highlight: neon ring + short motion trail ---------------------------
const KikaMarker: React.FC<{ srcT: number; cam: Cam; outW: number; outH: number; f: number; pulseAt: number[] }> = ({
  srcT, cam, outW, outH, f, pulseAt,
}) => {
  const vis = interpolate(srcT, [1.85, 2.05, 7.35, 7.6], [0, 1, 1, 0], clamp);
  if (vis <= 0) return null;
  const at = (t: number) =>
    toScreen(cam, outW, outH, interpolate(t, KIKA_TRACK.t, KIKA_TRACK.x, clamp), interpolate(t, KIKA_TRACK.t, KIKA_TRACK.y, clamp));
  const p = at(srcT);
  const pulse = pulseAt.reduce((acc, s) => acc + hit(f, s, 18), 0);
  const trail = Array.from({ length: 12 }, (_, i) => at(Math.max(1.85, srcT - i * 0.045)));
  const rx = 34 * p.k * (1 + 0.5 * pulse);
  const ry = 12 * p.k * (1 + 0.5 * pulse);
  return (
    <svg width={outW} height={outH} style={{ position: "absolute", left: 0, top: 0, opacity: vis, overflow: "visible" }}>
      {trail.slice(1).map((q, i) => (
        <line key={i} x1={trail[i].x} y1={trail[i].y} x2={q.x} y2={q.y} stroke={VOLT}
          strokeWidth={Math.max(1, (14 - i) * 0.9 * (p.k / 2))} strokeLinecap="round" opacity={0.75 * (1 - i / 12)} />
      ))}
      <ellipse cx={p.x} cy={p.y} rx={rx * 1.35} ry={ry * 1.35} fill="none" stroke={PINK} strokeWidth={3} opacity={0.35 + 0.6 * pulse} />
      <ellipse cx={p.x} cy={p.y} rx={rx} ry={ry} fill="none" stroke={VOLT} strokeWidth={5} style={{ filter: `drop-shadow(0 0 10px ${VOLT})` }} />
    </svg>
  );
};

// ---- particles -------------------------------------------------------------------
const Burst: React.FC<{ f: number; at: number; x: number; y: number; seed: string; count?: number }> = ({ f, at, x, y, seed, count = 46 }) => {
  const t = (f - at) / FPS;
  if (t < 0 || t > 1.4) return null;
  return (
    <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0, overflow: "visible", pointerEvents: "none" }}>
      {Array.from({ length: count }, (_, i) => {
        const a = random(`${seed}a${i}`) * Math.PI * 2;
        const v = 500 + random(`${seed}v${i}`) * 1100;
        const px = x + Math.cos(a) * v * t;
        const py = y + Math.sin(a) * v * t + 900 * t * t;
        const s = (8 + random(`${seed}s${i}`) * 18) * (1 - t / 1.4);
        const col = [VOLT, PINK, "#FFFFFF", "#29E6FF"][i % 4];
        return i % 3 === 0 ? (
          <circle key={i} cx={px} cy={py} r={s / 2} fill={col} />
        ) : (
          <rect key={i} x={px - s / 2} y={py - s / 4} width={s} height={s / 2} fill={col}
            transform={`rotate(${random(`${seed}r${i}`) * 360 + t * 720} ${px} ${py})`} />
        );
      })}
    </svg>
  );
};

// ---- stickers --------------------------------------------------------------------
const Pill: React.FC<{ bg: string; color: string; children: React.ReactNode; size?: number; style?: React.CSSProperties }> = ({
  bg, color, children, size = 52, style,
}) => (
  <div style={{
    display: "inline-block", backgroundColor: bg, color, fontFamily: COND, fontWeight: 800, fontSize: size,
    letterSpacing: size * 0.06, textTransform: "uppercase", padding: `${size * 0.12}px ${size * 0.42}px`,
    borderRadius: 10, boxShadow: `6px 6px 0 ${INK}`, lineHeight: 1.05, ...style,
  }}>
    {children}
  </div>
);

const GoalSticker: React.FC<{ f: number; at: number; y: number; len?: number }> = ({ f, at, y, len = 52 }) => {
  if (f < at || f > at + len) return null;
  const s = sp(f, at, 8, 0.7);
  const out = interpolate(f, [at + len - 12, at + len], [1, 0], { ...clamp, easing: Easing.in(Easing.back(2)) });
  return (
    <div style={{ position: "absolute", top: y, width: W, display: "flex", justifyContent: "center" }}>
      <div style={{
        fontFamily: COND, fontWeight: 800, fontSize: 250, lineHeight: 1, color: VOLT, letterSpacing: 4,
        WebkitTextStroke: `10px ${INK}`, paintOrder: "stroke fill", textShadow: `12px 12px 0 ${PINK}`,
        scale: s * out, rotate: `${-7 + 3 * Math.sin(f / 4)}deg`,
      }}>
        GOAL!
      </div>
    </div>
  );
};

const VsBadge: React.FC<{ f: number; at: number; size: number; y: number }> = ({ f, at, size, y }) => {
  const s = sp(f, at, 9, 0.6) * (1 + 0.06 * Math.sin((f - at) / 3.2));
  return (
    <div style={{
      position: "absolute", left: W / 2 - size / 2, top: y - size / 2, width: size, height: size, borderRadius: "50%",
      backgroundColor: INK, border: `${size * 0.07}px solid ${VOLT}`, boxShadow: `0 0 0 ${size * 0.05}px ${PINK}`,
      display: "flex", alignItems: "center", justifyContent: "center", scale: s, rotate: `${-8 + 4 * Math.sin(f / 6)}deg`,
    }}>
      <span style={{ fontFamily: COND, fontWeight: 800, fontSize: size * 0.46, color: VOLT, fontStyle: "italic" }}>VS</span>
    </div>
  );
};

// ---- scene A: dribble -------------------------------------------------------------
const FunKika: React.FC = () => {
  const f = useCurrentFrame();
  const srcT = A_SRC0 + (f / FPS) * A_RATE;
  const cam = kikaCam(srcT, 470, 608, W / H);
  const skillFrames = SKILLS.map(aFrame);
  const punch = 1 + skillFrames.reduce((a, s) => a + 0.16 * hit(f, s, 16), 0) + 0.12 * hit(f, KIKA_GOAL, 16);
  const shake = 26 * hit(f, KIKA_GOAL, 16) * Math.sin(f * 2.1);
  const rgb = 16 * hit(f, KIKA_GOAL, 12) + skillFrames.reduce((a, s) => a + 8 * hit(f, s, 8), 0);
  const gs = toScreen(cam, W, H, GOAL_SRC.x, GOAL_SRC.y);
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: INK }}>
      <RgbFilter id="rgbA" amount={rgb} />
      <AbsoluteFill style={{ scale: punch, translate: `${shake}px ${shake * 0.5}px`, filter: rgb > 0.5 ? "url(#rgbA)" : undefined }}>
        <Video src={staticFile("kika.mp4")} muted trimBefore={Math.round((A_SRC0 - KIKA_FILE_OFFSET) * FPS)} playbackRate={A_RATE}
          style={{ ...panelStyle(cam, KIKA_SRC_SIZE, W, H), filter: POP }} />
        <KikaMarker srcT={srcT} cam={cam} outW={W} outH={H} f={f} pulseAt={skillFrames} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0) 80%, rgba(0,0,0,0.75) 100%)" }} />
      <Burst f={f} at={KIKA_GOAL} x={gs.x} y={gs.y} seed="kg" />
    </AbsoluteFill>
  );
};

// ---- transition: diagonal slices ---------------------------------------------------
const Slices: React.FC = () => {
  const f = useCurrentFrame();
  const cols = [VOLT, PINK, INK, VOLT, PINK, INK];
  return (
    <AbsoluteFill style={{ overflow: "hidden", pointerEvents: "none" }}>
      {cols.map((c, i) => {
        const p = interpolate(f, [448 + i * 2, 464 + i * 2, 476 + i * 2, 490 + i * 2], [-1.3, 0, 0, 1.3], {
          ...clamp, easing: Easing.inOut(Easing.cubic),
        });
        return (
          <div key={i} style={{
            position: "absolute", left: -400, top: i * (H / cols.length) - 200, width: W + 800, height: H / cols.length + 120,
            backgroundColor: c, rotate: "-14deg", translate: `${p * (W + 900)}px 0px`,
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

// ---- scene S: split ----------------------------------------------------------------
const Half: React.FC<{ top: number; children: React.ReactNode }> = ({ top, children }) => (
  <div style={{ position: "absolute", left: 0, top, width: W, height: H / 2, overflow: "hidden", backgroundColor: INK }}>{children}</div>
);

const FunSplit: React.FC = () => {
  const f = useCurrentFrame(); // 0 at SPLIT_IN
  const g = SPLIT_GOAL - SPLIT_IN;
  const messiT = S_MESSI_SRC0 + (f / FPS) * S_MESSI_RATE;
  const kikaT = S_KIKA_SRC0 + (f / FPS) * S_KIKA_RATE;
  const kcam = kikaCam(kikaT, 720, 900, W / (H / 2));
  const punch = 1 + 0.1 * hit(f, g, 16);
  const shake = 22 * hit(f, g, 16) * Math.sin(f * 2.3);
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      <Half top={0}>
        <div style={{ position: "absolute", inset: 0, scale: punch, translate: `${shake}px 0px` }}>
          <Video src={staticFile("messi.mp4")} muted trimBefore={Math.round(S_MESSI_SRC0 * FPS)} playbackRate={S_MESSI_RATE}
            style={{ ...panelStyle(messiCam(messiT), MESSI_SRC_SIZE, W, H / 2), filter: POP }} />
        </div>
      </Half>
      <Half top={H / 2}>
        <div style={{ position: "absolute", inset: 0, scale: punch, translate: `${-shake}px 0px` }}>
          <Video src={staticFile("kika.mp4")} muted trimBefore={Math.round((S_KIKA_SRC0 - KIKA_FILE_OFFSET) * FPS)} playbackRate={S_KIKA_RATE}
            style={{ ...panelStyle(kcam, KIKA_SRC_SIZE, W, H / 2), filter: POP }} />
          <KikaMarker srcT={kikaT} cam={kcam} outW={W} outH={H / 2} f={f} pulseAt={[]} />
        </div>
      </Half>
      <div style={{ position: "absolute", left: 0, top: H / 2 - 7, width: W, height: 14, backgroundColor: VOLT, boxShadow: `0 0 24px ${VOLT}` }} />
    </AbsoluteFill>
  );
};

// ---- scene E: end ----------------------------------------------------------------
const FunEnd: React.FC = () => {
  const f = useCurrentFrame();
  const zoom = interpolate(f, [0, END - SPLIT_GOAL], [1.04, 1.12], clamp);
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      <Half top={0}>
        <div style={{ position: "absolute", inset: 0, scale: zoom }}>
          <Img src={staticFile("messi_goal.jpg")} style={{ ...panelStyle(messiCam(29.5), MESSI_SRC_SIZE, W, H / 2), filter: POP }} />
        </div>
      </Half>
      <Half top={H / 2}>
        <div style={{ position: "absolute", inset: 0, scale: zoom }}>
          <Img src={staticFile("kika_goal.jpg")} style={{ ...panelStyle(kikaCam(8.25, 720, 900, W / (H / 2)), KIKA_SRC_SIZE, W, H / 2), filter: POP }} />
        </div>
      </Half>
      <AbsoluteFill style={{ backgroundColor: INK, opacity: interpolate(f, [4, 20], [0, 0.35], clamp) }} />
      <div style={{ position: "absolute", left: 0, top: H / 2 - 7, width: W, height: 14, backgroundColor: VOLT }} />
    </AbsoluteFill>
  );
};

const bigName = (f: number, at: number, color: string, shadow: string): React.CSSProperties => ({
  fontFamily: COND, fontWeight: 800, fontSize: 230, lineHeight: 0.9, color, letterSpacing: 6, fontStyle: "italic",
  WebkitTextStroke: `9px ${INK}`, paintOrder: "stroke fill", textShadow: `10px 10px 0 ${shadow}`,
  scale: sp(f, at, 9, 0.7), rotate: "-5deg",
});

// ---- overlays --------------------------------------------------------------------
const Overlays: React.FC = () => {
  const f = useCurrentFrame();
  const inA = (s: number, e: number) => sp(f, s) * interpolate(f, [e - 8, e], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* dribble: name sticker */}
      <div style={{ position: "absolute", left: 64, top: 1420, scale: inA(18, 392), rotate: "-4deg", transformOrigin: "left center" }}>
        <Pill bg={VOLT} color={INK} size={64}>Kika Nazareth</Pill>
        <div style={{ marginTop: 14, marginLeft: 8 }}><Pill bg={PINK} color="#fff" size={40}>FC 27 · #5</Pill></div>
      </div>
      <GoalSticker f={f} at={KIKA_GOAL} y={760} />
      {/* split: badges + VS */}
      {f >= SPLIT_IN && f < SPLIT_GOAL && (
        <>
          <div style={{ position: "absolute", left: 56, top: 230, scale: sp(f, SPLIT_IN + 16), rotate: "-3deg", transformOrigin: "left center" }}>
            <Pill bg={BARCA} color="#fff" size={50}>Messi · 2007</Pill>
          </div>
          <div style={{ position: "absolute", left: 56, top: 1500, scale: sp(f, SPLIT_IN + 24), rotate: "-3deg", transformOrigin: "left center" }}>
            <Pill bg={VOLT} color={INK} size={50}>Kika · FC 27</Pill>
          </div>
          <VsBadge f={f} at={SPLIT_IN + 8} size={170} y={H / 2} />
        </>
      )}
      <GoalSticker f={f} at={SPLIT_GOAL} y={H / 2 - 125} len={34} />
      {/* end */}
      {f >= SPLIT_GOAL + 36 && (
        <>
          <div style={{ position: "absolute", top: 520, width: W, textAlign: "center" }}>
            <span style={bigName(f, SPLIT_GOAL + 36, "#fff", BARCA)}>MESSI</span>
          </div>
          <div style={{ position: "absolute", top: 1190, width: W, textAlign: "center" }}>
            <span style={bigName(f, SPLIT_GOAL + 44, VOLT, PINK)}>KIKA</span>
          </div>
          <VsBadge f={f} at={SPLIT_GOAL + 40} size={230} y={H / 2} />
        </>
      )}
    </AbsoluteFill>
  );
};

const FunSound: React.FC = () => {
  const sfx = (file: string, at: number, volume: number) => (
    <Sequence from={at} layout="none"><Audio src={staticFile(`sfx/${file}.wav`)} volume={volume} /></Sequence>
  );
  return (
    <>
      <Audio src={staticFile("commentary.wav")} trimBefore={Math.round(1.1 * FPS)}
        volume={(fr) => interpolate(fr, [0, 8, END - 40, END], [0, 1, 1, 0], clamp)} />
      {sfx("pop", 18, 0.5)}
      {SKILLS.map((s) => <React.Fragment key={s}>{sfx("whoosh", aFrame(s) - 8, 0.35)}</React.Fragment>)}
      {sfx("impact", KIKA_GOAL - 1, 0.5)}
      {sfx("pop", KIKA_GOAL + 1, 0.45)}
      {sfx("whoosh", 446, 0.55)}
      {sfx("whoosh", 470, 0.4)}
      {sfx("pop", SPLIT_IN + 8, 0.4)}
      {sfx("pop", SPLIT_IN + 16, 0.35)}
      {sfx("pop", SPLIT_IN + 24, 0.35)}
      {sfx("impact", SPLIT_GOAL - 1, 0.55)}
      {sfx("pop", SPLIT_GOAL + 1, 0.45)}
      {sfx("pop", SPLIT_GOAL + 36, 0.4)}
      {sfx("pop", SPLIT_GOAL + 44, 0.4)}
      {sfx("boom", SPLIT_GOAL + 40, 0.35)}
    </>
  );
};

export const KikaMessiFun: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: INK }}>
    <Sequence durationInFrames={SPLIT_IN + 12} name="Kika dribble"><FunKika /></Sequence>
    <Sequence from={SPLIT_IN} durationInFrames={SPLIT_GOAL - SPLIT_IN} name="Split"><FunSplit /></Sequence>
    <Sequence from={SPLIT_GOAL} durationInFrames={END - SPLIT_GOAL} name="End"><FunEnd /></Sequence>
    <Slices />
    <Overlays />
    <FunSound />
  </AbsoluteFill>
);

export const FunComposition = () => (
  <Composition id="KikaMessiFun" component={KikaMessiFun} durationInFrames={END} fps={FPS} width={W} height={H} />
);
