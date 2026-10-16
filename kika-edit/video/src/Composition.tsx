import { loadFont } from "@remotion/fonts";
import { Audio, Video } from "@remotion/media";
import React from "react";
import {
  AbsoluteFill,
  Composition,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { KIKA_TRACK } from "./data/kikaTrack";

const FPS = 30;
const W = 1080;
const H = 1920;

// ---- timeline (frames) -------------------------------------------------------
const KIKA_GOAL = 396; // ball crosses the line, lands on the commentator's scream
const SPLIT_IN = 470; // split screen arrives behind the flash
const SPLIT_GOAL = 720; // both goals hit together
const END = 810;

// Kika clip in public/ starts 1.0s into the original replay.
const KIKA_FILE_OFFSET = 1.0;
const KIKA_SRC_SIZE = { w: 1920, h: 1080 };
const MESSI_SRC_SIZE = { w: 1024, h: 576 };

// Full-screen dribble: source 1.6s -> 8.2s at half speed.
const A_SRC0 = 1.6;
const A_RATE = 0.5;
// Split: Kika 2.0s -> 8.2s and Messi's close-up replay 15.6s -> 29.5s, both into 8s.
const S_KIKA_SRC0 = 2.0;
const S_KIKA_RATE = (8.2 - 2.0) / ((SPLIT_GOAL - SPLIT_IN) / FPS);
const S_MESSI_SRC0 = 15.6;
const S_MESSI_RATE = (29.5 - 15.6) / ((SPLIT_GOAL - SPLIT_IN) / FPS);

// Messi's horizontal position (source px) through the replay, read off a gridded contact sheet.
const MESSI_X: [number, number][] = [
  [15.6, 617], [16.5, 694], [17.5, 555], [18.0, 361], [18.5, 300], [19.0, 640], [19.5, 571],
  [20.5, 694], [22.0, 768], [23.0, 685], [24.5, 719], [25.0, 552], [26.0, 400], [26.5, 709],
  [27.0, 900], [28.0, 800], [29.0, 880], [29.5, 586],
];

const CREAM = "#F2EDE3";
const COND = "Barlow Condensed";

loadFont({ family: COND, url: staticFile("fonts/BarlowCondensed_600SemiBold.ttf"), weight: "600" });
loadFont({ family: COND, url: staticFile("fonts/BarlowCondensed_800ExtraBold.ttf"), weight: "800" });

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const smooth = (x: number) => x * x * (3 - 2 * x);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

type Cam = { cx: number; cy: number; cw: number };

// Kika camera: follow the tracked marker, then widen towards the goal as she shoots.
const kikaCam = (srcT: number, baseW: number, wideW: number, aspect: number): Cam => {
  const tx = interpolate(srcT, KIKA_TRACK.t, KIKA_TRACK.x, clamp);
  const ty = interpolate(srcT, KIKA_TRACK.t, KIKA_TRACK.y, clamp);
  const w = smooth(interpolate(srcT, [7.25, 7.85], [0, 1], clamp));
  const cw = lerp(baseW, wideW, w);
  const ch = cw / aspect;
  // Keep the game's top bar and minimap (y > 860) out of the tight shot; allow full height once wide.
  const lo = lerp(25, 0, w) + ch / 2;
  const hi = lerp(860, KIKA_SRC_SIZE.h, w) - ch / 2;
  const cy = lo <= hi ? Math.min(Math.max(lerp(ty, 540, w), lo), hi) : (lo + hi) / 2;
  return {
    cx: Math.min(Math.max(lerp(tx, 560, w), cw / 2), KIKA_SRC_SIZE.w - cw / 2),
    cy,
    cw,
  };
};

const messiCam = (t: number): Cam => {
  const cw = 648; // full height, panel aspect 1.125
  const x = interpolate(t, MESSI_X.map((k) => k[0]), MESSI_X.map((k) => k[1]), {
    ...clamp,
    easing: Easing.inOut(Easing.quad),
  });
  return { cx: Math.min(Math.max(x, cw / 2), MESSI_SRC_SIZE.w - cw / 2), cy: 288, cw };
};

// Positions a source frame so that the camera window (cw wide, centred on cx/cy) fills the panel.
const panelStyle = (cam: Cam, src: { w: number; h: number }, outW: number, outH: number): React.CSSProperties => {
  const k = outW / cam.cw;
  const ch = outH / k;
  return {
    position: "absolute",
    width: src.w * k,
    height: src.h * k,
    left: -(cam.cx - cam.cw / 2) * k,
    top: -(cam.cy - ch / 2) * k,
  };
};

const GRADE: React.CSSProperties = { filter: "contrast(1.08) saturate(0.94) brightness(0.98)" };

const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.55 }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(ellipse 75% 60% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${strength}) 100%)`,
      pointerEvents: "none",
    }}
  />
);

// ---- scene A: Kika's dribble, full screen -------------------------------------
const KikaFull: React.FC = () => {
  const f = useCurrentFrame();
  const srcT = A_SRC0 + (f / FPS) * A_RATE;
  const cam = kikaCam(srcT, 470, 608, W / H);
  const punch = interpolate(f, [KIKA_GOAL, KIKA_GOAL + 12], [1.07, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const shake = f >= KIKA_GOAL ? Math.sin((f - KIKA_GOAL) * 2.3) * 14 * Math.exp(-(f - KIKA_GOAL) / 6) : 0;
  // zoom-through into the transition
  const through = interpolate(f, [450, 476], [1, 2.4], { ...clamp, easing: Easing.in(Easing.cubic) });
  const blur = interpolate(f, [452, 476], [0, 18], clamp);
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "black" }}>
      <AbsoluteFill
        style={{
          scale: punch * through,
          translate: `${shake}px ${shake * 0.6}px`,
          filter: `blur(${blur}px)`,
        }}
      >
        <Video
          src={staticFile("kika.mp4")}
          muted
          trimBefore={Math.round((A_SRC0 - KIKA_FILE_OFFSET) * FPS)}
          playbackRate={A_RATE}
          style={{ ...panelStyle(cam, KIKA_SRC_SIZE, W, H), ...GRADE }}
        />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0) 72%, rgba(0,0,0,0.88) 92%, rgba(0,0,0,0.95) 100%)" }} />
      <Vignette />
    </AbsoluteFill>
  );
};

// ---- scene S: split screen, Messi 2007 over Kika ------------------------------
const Panel: React.FC<{ children: React.ReactNode; top: number }> = ({ children, top }) => (
  <div style={{ position: "absolute", left: 0, top, width: W, height: H / 2, overflow: "hidden", backgroundColor: "black" }}>
    {children}
  </div>
);

const Split: React.FC = () => {
  const f = useCurrentFrame(); // 0 at SPLIT_IN
  const messiT = S_MESSI_SRC0 + (f / FPS) * S_MESSI_RATE;
  const kikaT = S_KIKA_SRC0 + (f / FPS) * S_KIKA_RATE;
  const slide = interpolate(f, [0, 18], [1, 0], { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const goal = SPLIT_GOAL - SPLIT_IN;
  const punch = interpolate(f, [goal, goal + 12], [1.06, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Panel top={-slide * (H / 2)}>
        <div style={{ position: "absolute", inset: 0, scale: punch }}>
          <Video
            src={staticFile("messi.mp4")}
            muted
            trimBefore={Math.round(S_MESSI_SRC0 * FPS)}
            playbackRate={S_MESSI_RATE}
            style={{ ...panelStyle(messiCam(messiT), MESSI_SRC_SIZE, W, H / 2), ...GRADE }}
          />
        </div>
      </Panel>
      <Panel top={H / 2 + slide * (H / 2)}>
        <div style={{ position: "absolute", inset: 0, scale: punch }}>
          <Video
            src={staticFile("kika.mp4")}
            muted
            trimBefore={Math.round((S_KIKA_SRC0 - KIKA_FILE_OFFSET) * FPS)}
            playbackRate={S_KIKA_RATE}
            style={{ ...panelStyle(kikaCam(kikaT, 720, 900, W / (H / 2)), KIKA_SRC_SIZE, W, H / 2), ...GRADE }}
          />
        </div>
      </Panel>
      <div style={{ position: "absolute", left: 0, top: H / 2 - 3, width: W, height: 6, backgroundColor: CREAM, opacity: 1 - slide }} />
      <Vignette strength={0.45} />
    </AbsoluteFill>
  );
};

// ---- scene E: end card over frozen goal frames --------------------------------
const EndCard: React.FC = () => {
  const f = useCurrentFrame();
  const dim = interpolate(f, [6, 30], [0, 0.62], clamp);
  const drift = interpolate(f, [0, END - SPLIT_GOAL], [1, 1.06], clamp);
  const messiStill = panelStyle(messiCam(29.5), MESSI_SRC_SIZE, W, H / 2);
  const kikaStill = panelStyle(kikaCam(8.25, 720, 900, W / (H / 2)), KIKA_SRC_SIZE, W, H / 2);
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Panel top={0}>
        <div style={{ position: "absolute", inset: 0, scale: drift }}>
          <Img src={staticFile("messi_goal.jpg")} style={{ ...messiStill, ...GRADE }} />
        </div>
      </Panel>
      <Panel top={H / 2}>
        <div style={{ position: "absolute", inset: 0, scale: drift }}>
          <Img src={staticFile("kika_goal.jpg")} style={{ ...kikaStill, ...GRADE }} />
        </div>
      </Panel>
      <AbsoluteFill style={{ backgroundColor: "black", opacity: dim }} />
      <Vignette strength={0.6} />
    </AbsoluteFill>
  );
};

// ---- typography ---------------------------------------------------------------
const reveal = (f: number, start: number, end: number, len = 14) => ({
  opacity: interpolate(f, [start, start + len, end - 10, end], [0, 1, 1, 0], clamp),
  translate: `0px ${interpolate(f, [start, start + len + 6], [26, 0], { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) })}px`,
  filter: `blur(${interpolate(f, [start, start + len], [10, 0], clamp)}px)`,
});

const label = (size: number, weight = 600): React.CSSProperties => ({
  fontFamily: COND,
  fontWeight: weight,
  fontSize: size,
  letterSpacing: size * 0.22,
  textTransform: "uppercase",
  color: CREAM,
  textShadow: "0 2px 14px rgba(0,0,0,0.6)",
});

const Titles: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* name tag during the dribble */}
      <div style={{ position: "absolute", left: 72, top: 1440, ...reveal(f, 160, 380) }}>
        <div style={{ width: interpolate(f, [160, 190], [0, 120], clamp), height: 4, backgroundColor: CREAM, marginBottom: 18 }} />
        <div style={label(58, 800)}>Kika Nazareth</div>
        <div style={{ ...label(32), opacity: 0.75, marginTop: 6 }}>FC 27 · No. 5</div>
      </div>
      {/* panel labels */}
      <div style={{ position: "absolute", left: 72, top: 236, ...reveal(f, 500, SPLIT_GOAL + 2) }}>
        <div style={label(40, 800)}>Lionel Messi</div>
        <div style={{ ...label(28), opacity: 0.75, marginTop: 4 }}>vs Getafe · 2007</div>
      </div>
      <div style={{ position: "absolute", left: 72, top: 1490, ...reveal(f, 510, SPLIT_GOAL + 2) }}>
        <div style={label(40, 800)}>Kika Nazareth</div>
        <div style={{ ...label(28), opacity: 0.75, marginTop: 4 }}>FC 27 · 2026</div>
      </div>
      {/* end card */}
      <div style={{ position: "absolute", top: H / 2 - 24, width: W, textAlign: "center" }}>
        <div style={{ ...label(34), ...reveal(f, SPLIT_GOAL + 20, END + 20, 16) }}>
          <span style={{ opacity: 0.8 }}>Messi 2007 — Nazareth 2026</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---- flashes -----------------------------------------------------------------
const Flashes: React.FC = () => {
  const f = useCurrentFrame();
  const a =
    interpolate(f, [462, 472, 482], [0, 1, 0], clamp); // transition into the split only
  return <AbsoluteFill style={{ backgroundColor: CREAM, opacity: Math.min(a, 1), pointerEvents: "none" }} />;
};

// ---- sound --------------------------------------------------------------------
const Sound: React.FC = () => (
  <>
    {/* the original Messi commentary, from just before he picks up the ball */}
    <Audio
      src={staticFile("commentary.wav")}
      trimBefore={Math.round(1.1 * FPS)}
      volume={(f) => interpolate(f, [0, 8, END - 40, END], [0, 1, 1, 0], clamp)}
    />
    <Sequence from={KIKA_GOAL - 1} layout="none"><Audio src={staticFile("sfx/impact.wav")} volume={0.55} /></Sequence>
    <Sequence from={472 - 45} layout="none"><Audio src={staticFile("sfx/riser.wav")} volume={0.35} /></Sequence>
    <Sequence from={458} layout="none"><Audio src={staticFile("sfx/whoosh.wav")} volume={0.6} /></Sequence>
    <Sequence from={471} layout="none"><Audio src={staticFile("sfx/impact.wav")} volume={0.4} /></Sequence>
    <Sequence from={SPLIT_GOAL - 1} layout="none"><Audio src={staticFile("sfx/impact.wav")} volume={0.6} /></Sequence>
    <Sequence from={SPLIT_GOAL + 14} layout="none"><Audio src={staticFile("sfx/boom.wav")} volume={0.45} /></Sequence>
  </>
);

export const KikaMessi: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "black" }}>
    <Sequence durationInFrames={SPLIT_IN + 10} name="Kika dribble">
      <KikaFull />
    </Sequence>
    <Sequence from={SPLIT_IN} durationInFrames={SPLIT_GOAL - SPLIT_IN} name="Split: Messi / Kika">
      <Split />
    </Sequence>
    <Sequence from={SPLIT_GOAL} durationInFrames={END - SPLIT_GOAL} name="End card">
      <EndCard />
    </Sequence>
    <Flashes />
    <Titles />
    <Sound />
  </AbsoluteFill>
);

export const MyComposition = () => (
  <Composition id="KikaMessi" component={KikaMessi} durationInFrames={END} fps={FPS} width={W} height={H} />
);
