import subprocess, json, sys, numpy as np
SRC = "/home/user/my-app/kika-edit/src/kika.mp4"
def frames(t0, t1, fps=30):
    p = subprocess.Popen(["ffmpeg","-loglevel","error","-ss",str(t0),"-t",str(t1-t0),"-i",SRC,"-vf",f"fps={fps}",
                          "-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(1920*1080*3)
        if len(b) < 1920*1080*3: break
        yield t0 + i/fps, np.frombuffer(b, np.uint8).reshape(1080,1920,3)
        i += 1
def label(mask):
    # tiny connected-components (4-neighbour) via flood fill on candidate pixels only
    ys, xs = np.nonzero(mask); seen = set(); comps = []
    pts = set(zip(ys.tolist(), xs.tolist()))
    for p in pts:
        if p in seen: continue
        stack=[p]; seen.add(p); c=[]
        while stack:
            y,x = stack.pop(); c.append((y,x))
            for q in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
                if q in pts and q not in seen: seen.add(q); stack.append(q)
        comps.append(np.array(c))
    return comps
if sys.argv[1] == "probe":
    t = float(sys.argv[2]); x0,y0 = int(sys.argv[3]), int(sys.argv[4])
    for _, f in frames(t, t+0.04):
        patch = f[y0-12:y0+12, x0-12:x0+12].reshape(-1,3).astype(int)
        pink = patch[(patch[:,0]>150)&(patch[:,0]-patch[:,1]>90)]
        print("pink px", len(pink), "median", np.median(pink,0) if len(pink) else None, "min", pink.min(0) if len(pink) else None, "max", pink.max(0) if len(pink) else None)
    sys.exit()
t0, t1 = float(sys.argv[2]), float(sys.argv[3]); prev = tuple(map(float, sys.argv[4:6])); out=[]
for t, f in frames(t0, t1):
    a = f.astype(int); r,g,b = a[...,0],a[...,1],a[...,2]
    m = (r>170)&(g<110)&(b>80)&(b<190)&(r-b>40)&(r-g>100)
    m[:60] = False; m[940:] = False                     # ignore HUD bands
    best=None
    for c in label(m):
        n=len(c)
        if not (25 <= n <= 260): continue
        h = np.ptp(c[:,0])+1; w = np.ptp(c[:,1])+1
        if not (0.8 <= w/h <= 2.6): continue
        cy, cx = c[:,0].mean(), c[:,1].mean()
        d = np.hypot(cx-prev[0], cy-prev[1])
        if d < 160 and (best is None or d < best[0]): best=(d,cx,cy,n)
    if best: prev=(best[1],best[2]); out.append((round(t,3), round(best[1],1), round(best[2],1), best[3]))
    else: out.append((round(t,3), None, None, 0))
json.dump(out, open(sys.argv[6],"w"))
miss=sum(1 for o in out if o[1] is None); print(f"{len(out)} frames, {miss} missed")
for o in out[::15]: print(o)
