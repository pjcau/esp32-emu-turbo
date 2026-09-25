#!/usr/bin/env python3
"""Build the web preview of the launcher boot splash from the firmware source.

The splash (retro-go/launcher/main/splash.c) is procedural: splash_render()
and splash_sample() are pure functions, so the same file compiles on the
host with -DSPLASH_HOST. This script compiles it with gcc, dumps all
frames and the jingle, and writes:

    website/static/boot-splash.html   playable preview (frames + audio embedded)

The preview is therefore the board's output, not a re-drawing of it.
`boot-splash.html#embed` shows only the player (used by the docs iframe).

Usage:
    python3 scripts/generate_splash_preview.py      (or: make splash-preview)

Needs gcc and Pillow.
"""
import base64
import io
import os
import re
import subprocess
import sys
import tempfile
import wave

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLASH_C = os.path.join(ROOT, "retro-go", "launcher", "main", "splash.c")
SPLASH_H = os.path.join(ROOT, "retro-go", "launcher", "main", "splash.h")
OUT_HTML = os.path.join(ROOT, "website", "static", "boot-splash.html")

HOST_C = r"""
#define SPLASH_HOST
#include "%s"
#include <stdio.h>
static int check(const glyph_t *f, int n, int h)
{
    int bad = 0;
    for (int i = 0; i < n; i++)
        if (f[i].rows && (int)strlen(f[i].rows) != f[i].w * h)
        {
            fprintf(stderr, "glyph '%%c': %%zu chars, want %%d\n", f[i].ch, strlen(f[i].rows), f[i].w * h);
            bad = 1;
        }
    return bad;
}
int main(int argc, char **argv)
{
    if (argc < 3 || (check(big_font, BIG_COUNT, 7) | check(small_font, SMALL_COUNT, 5)))
        return 1;
    static uint8_t buf[W * H];
    FILE *fv = fopen(argv[1], "wb");
    for (int f = 0; f < SPLASH_FRAMES; f++)
    {
        splash_render(buf, f);
        fwrite(buf, 1, sizeof buf, fv);
    }
    fclose(fv);
    FILE *fa = fopen(argv[2], "wb");
    for (int n = 0; n < SPLASH_FRAMES * SPLASH_RATE / SPLASH_FPS; n++)
    {
        int16_t v = (int16_t)(splash_sample(n) * 26000.f);
        fwrite(&v, 2, 1, fa);
    }
    fclose(fa);
    return 0;
}
"""


def header_int(src, name):
    return int(re.search(r"#define\s+%s\s+(\d+)" % name, src).group(1))


def main():
    csrc = open(SPLASH_C).read()
    hsrc = open(SPLASH_H).read()
    W, H = header_int(hsrc, "SPLASH_WIDTH"), header_int(hsrc, "SPLASH_HEIGHT")
    N, FPS, RATE = header_int(hsrc, "SPLASH_FRAMES"), header_int(hsrc, "SPLASH_FPS"), header_int(hsrc, "SPLASH_RATE")
    T = {k: header_int(csrc, k) for k in ("T_FLASH", "T_HOLD", "T_SHINE1", "T_SHINE2", "T_FOOTER", "T_CLOSE", "T_BLACK")}
    pal = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{6})",
                                         re.search(r"splash_palette\[16\] = \{(.*?)\};", csrc, re.S).group(1))]
    flat = [v for c in pal for v in (c >> 16, (c >> 8) & 255, c & 255)]

    with tempfile.TemporaryDirectory() as tmp:
        host_c, host = os.path.join(tmp, "host.c"), os.path.join(tmp, "host")
        frames_raw, audio_raw = os.path.join(tmp, "frames.raw"), os.path.join(tmp, "audio.raw")
        open(host_c, "w").write(HOST_C % SPLASH_C)
        subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-o", host, host_c, "-lm"], check=True)
        subprocess.run([host, frames_raw, audio_raw], check=True)
        raw = open(frames_raw, "rb").read()
        pcm = open(audio_raw, "rb").read()

    sheet = Image.frombytes("P", (W, H * N), raw)
    sheet.putpalette(flat)
    buf = io.BytesIO()
    sheet.save(buf, "PNG", optimize=True)
    png_b64 = base64.b64encode(buf.getvalue()).decode()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    wav_b64 = base64.b64encode(buf.getvalue()).decode()

    def s(frame):
        return "%.2f s" % (frame / FPS)

    page = (TEMPLATE
            .replace("__PNG__", png_b64).replace("__WAV__", wav_b64)
            .replace("__N__", str(N)).replace("__FPS__", str(FPS)).replace("__W__", str(W)).replace("__H__", str(H))
            .replace("__MID__", str((T["T_HOLD"] + T["T_CLOSE"]) // 2))
            .replace("__SEGS__", "[[0,%d,'rings','#83769c'],[%d,%d,'flash','#fff1e8'],[%d,%d,'title hold','#ffa300'],"
                     "[%d,%d,'close','#ff77a8'],[%d,%d,'','#1d2b53']]"
                     % (T["T_FLASH"], T["T_FLASH"], T["T_HOLD"], T["T_HOLD"], T["T_CLOSE"], T["T_CLOSE"], T["T_BLACK"],
                        T["T_BLACK"], N))
            .replace("__T_FLASH__", s(T["T_FLASH"])).replace("__T_SHINE1__", s(T["T_SHINE1"]))
            .replace("__T_FOOTER__", s(T["T_FOOTER"])).replace("__T_SHINE2__", s(T["T_SHINE2"]))
            .replace("__T_CLOSE__", s(T["T_CLOSE"])).replace("__T_END__", s(N))
            .replace("__SECONDS__", str(N // FPS)))
    open(OUT_HTML, "w").write(page)
    print("wrote %s (%d KB)" % (os.path.relpath(OUT_HTML, ROOT), len(page) // 1024))
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Game Bro! Boot Splash</title>
<!-- Generated by scripts/generate_splash_preview.py from retro-go/launcher/main/splash.c. Do not edit. -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  color-scheme: dark;
  --ground:#0b1020; --panel:#131a31; --line:#26304f; --ink:#fff1e8; --muted:#9a90b3;
  --orange:#ffa300; --pink:#ff77a8; --red:#ff004d; --yellow:#ffec27; --blue:#29adff;
  --display:"Silkscreen", "Courier New", monospace;
  --body:"IBM Plex Sans", system-ui, sans-serif;
  --mono:"IBM Plex Mono", ui-monospace, monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.55 var(--body);padding-inline:16px;padding-block:32px 48px}
body.embed{padding-block:16px}
body.embed .page-only{display:none}
.wrap{max-width:980px;margin:0 auto;display:grid;gap:24px}
header{display:grid;gap:6px}
.eyebrow{font:500 12px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font:700 clamp(28px,5vw,44px)/1.1 var(--display);margin:0;text-wrap:balance;
  background:linear-gradient(180deg,var(--yellow) 0 35%,var(--orange) 35% 65%,var(--red) 65%);-webkit-background-clip:text;background-clip:text;color:transparent}
.lede{margin:0;max-width:62ch;color:var(--muted)}
.bezel{background:#05070f;border:1px solid var(--line);border-radius:14px;padding:clamp(10px,2.4vw,22px)}
canvas{display:block;width:100%;max-width:100%;aspect-ratio:3/2;image-rendering:pixelated;background:#000;border-radius:4px}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px}
button{font:700 14px var(--display);letter-spacing:.04em;color:#0b1020;background:var(--orange);border:0;border-radius:6px;padding:10px 18px;cursor:pointer}
button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
button:hover{filter:brightness(1.1)}
button:focus-visible,input:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.readout{font:500 13px var(--mono);font-variant-numeric:tabular-nums;color:var(--muted);margin-left:auto}
.scrub{display:grid;gap:8px}
input[type=range]{width:100%;accent-color:var(--pink)}
.timeline{position:relative;height:30px;border-radius:5px;overflow:hidden;display:flex;border:1px solid var(--line)}
.seg{height:100%;display:flex;align-items:center;padding-inline:6px;font:500 11px var(--mono);white-space:nowrap;overflow:hidden;color:#0b1020;cursor:pointer}
.marks{position:relative;height:18px;font:500 11px var(--mono);color:var(--muted);font-variant-numeric:tabular-nums}
.marks span{position:absolute;transform:translateX(-50%)}
.cursor{position:absolute;top:0;bottom:0;width:2px;background:var(--ink);pointer-events:none}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;display:grid;gap:10px;align-content:start}
.card h2{font:700 15px var(--display);margin:0;color:var(--pink);letter-spacing:.03em}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 16px}
dt{color:var(--muted);font:400 13px var(--mono)}
dd{margin:0;font-variant-numeric:tabular-nums}
ol{margin:0;padding-left:0;list-style:none;display:grid;gap:8px}
ol li{display:grid;grid-template-columns:5.5em 1fr;gap:10px}
ol b{font:500 13px var(--mono);color:var(--orange);font-weight:500;font-variant-numeric:tabular-nums}
code{font:13px var(--mono);color:var(--yellow)}
footer{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<div class="wrap">
  <header class="page-only">
    <div class="eyebrow">ESP32 Emu Turbo &middot; retro-go launcher</div>
    <h1>GAME BRO! boot splash</h1>
    <p class="lede">The intro the console plays on power-on before the launcher. Every frame and every sample here comes from the same <code>splash.c</code> that runs on the ESP32-S3, compiled on a PC. Press play with sound on.</p>
  </header>

  <div class="bezel"><canvas id="screen" width="480" height="320" aria-label="Splash animation"></canvas></div>

  <div class="controls">
    <button id="play" type="button">&#9654; Play with sound</button>
    <button id="loop" class="ghost" type="button" aria-pressed="false">Loop: off</button>
    <span class="readout" id="readout"></span>
  </div>

  <div class="scrub">
    <label class="eyebrow" for="frame">Scrub frames</label>
    <input id="frame" type="range" min="0" max="__N__" value="__MID__">
    <div class="timeline" id="timeline"></div>
    <div class="marks" id="marks"></div>
  </div>

  <div class="grid page-only">
    <section class="card">
      <h2>Timeline</h2>
      <ol>
        <li><b>0.00 s</b><span>Thin rings drift into the centre while the lit area shrinks to it. Soft square-wave sweep, 110 to 880 Hz.</span></li>
        <li><b>__T_FLASH__</b><span>White flash out of the centre. The title unmasks from its middle row. "Pling" arpeggio into an E major chord, with echo.</span></li>
        <li><b>__T_SHINE1__</b><span>First shine across the title, with a sparkle. Footer dithers in at __T_FOOTER__.</span></li>
        <li><b>__T_SHINE2__</b><span>Second shine.</span></li>
        <li><b>__T_CLOSE__</b><span>Everything closes back into the centre, then black. Retro-go starts at __T_END__.</span></li>
      </ol>
    </section>
    <section class="card">
      <h2>On the board</h2>
      <dl>
        <dt>Panel</dt><dd>ILI9488, 480 &times; 320</dd>
        <dt>Canvas</dt><dd>__W__ &times; __H__, drawn 2&times;</dd>
        <dt>Rate</dt><dd>__FPS__ fps, __N__ frames (__SECONDS__ s)</dd>
        <dt>Palette</dt><dd>16 colours, Bayer-dithered fades</dd>
        <dt>Audio</dt><dd>32 kHz, square + triangle</dd>
        <dt>Flash cost</dt><dd>about 7 KB, no asset files</dd>
        <dt>Plays</dt><dd>cold boot only</dd>
        <dt>Skip</dt><dd>any button</dd>
      </dl>
    </section>
  </div>

  <footer class="page-only">Generated from <code>retro-go/launcher/main/splash.c</code> by <code>scripts/generate_splash_preview.py</code>.</footer>
</div>

<script>
(function(){
  var N=__N__, FPS=__FPS__, W=__W__, H=__H__, MID=__MID__;
  if (location.hash === '#embed') document.body.classList.add('embed');
  var sheet=new Image(); sheet.src="data:image/png;base64,__PNG__";
  var audio=new Audio("data:audio/wav;base64,__WAV__");
  var cv=document.getElementById('screen'), ctx=cv.getContext('2d');
  var range=document.getElementById('frame'), readout=document.getElementById('readout');
  var playBtn=document.getElementById('play'), loopBtn=document.getElementById('loop');
  var loop=false, playing=false;
  range.max=N-1;
  var segs=__SEGS__;
  var tl=document.getElementById('timeline'), marks=document.getElementById('marks');
  segs.forEach(function(s){var d=document.createElement('div');d.className='seg';d.style.width=((s[1]-s[0])/N*100)+'%';d.style.background=s[3];d.textContent=s[2];d.onclick=function(){stop();show(Math.round((s[0]+s[1])/2));};tl.appendChild(d);});
  var cursor=document.createElement('div');cursor.className='cursor';tl.appendChild(cursor);
  for(var t=0;t<=N/FPS;t++){var m=document.createElement('span');m.style.left=(t*FPS/N*100)+'%';m.textContent=t+' s';if(t===0)m.style.transform='none';if(t*FPS>=N)m.style.transform='translateX(-100%)';marks.appendChild(m);}
  ctx.imageSmoothingEnabled=false;
  function pad(n){return String(n).padStart(3,'0');}
  function show(f){
    f=Math.max(0,Math.min(N-1,f));
    if(sheet.complete) ctx.drawImage(sheet,0,f*H,W,H,0,0,480,320);
    range.value=f; cursor.style.left=(f/N*100)+'%';
    readout.textContent='frame '+pad(f+1)+' / '+N+' · '+(f/FPS).toFixed(2)+' s';
  }
  function stop(){playing=false;audio.pause();playBtn.innerHTML='&#9654; Play with sound';}
  function tick(){
    if(!playing) return;
    var f=Math.floor(audio.currentTime*FPS);
    if(audio.ended||f>=N){
      if(loop){audio.currentTime=0;audio.play().catch(function(){});f=0;}
      else{stop();show(MID);return;}
    }
    show(f); requestAnimationFrame(tick);
  }
  playBtn.onclick=function(){
    if(playing){stop();return;}
    audio.currentTime=0; playing=true; playBtn.innerHTML='&#9632; Stop';
    audio.play().catch(function(){}); tick();
  };
  loopBtn.onclick=function(){loop=!loop;loopBtn.setAttribute('aria-pressed',loop);loopBtn.textContent='Loop: '+(loop?'on':'off');};
  range.oninput=function(){stop();show(+range.value);};
  sheet.onload=function(){show(MID);};
  show(MID);
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
