// Explainer reels: flat hand-drawn illustration style (cream paper, coral + black line art, dotted shadows),
// a headline that builds word by word with italic serif accent words, and one animated scene per sentence.
// Python calls window.load(reel) once, then window.frame(t) for every frame and gets a JPEG back.
const W = 1080, H = 1920;
const cv = document.getElementById("c");
const ctx = cv.getContext("2d");
const C = {
  bg: "#F3EEE7", dot: "#E6DED4", ink: "#1E1A1A", coral: "#DE6B57", pink: "#F6DCD4", white: "#FFFFFF",
  gray: "#8C847D", light: "#EFE8E0", gold: "#E8B64C", dark: "#1C1819", darkDot: "#2A2427", wood: "#3B2A23",
};
const SANS = "SG, Poppins, sans-serif", SERIF = "IS, serif", MONO = "SM, monospace";
let REEL = null, BG = null, BGD = null, DOTS = null, LAYOUT = {}, STAMPS = {};

// ---------- small maths ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const eOut = x => 1 - Math.pow(1 - clamp(x), 3);
const eInOut = x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const eBack = x => { x = clamp(x); const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const prog = (t, a, d) => clamp((t - a) / d);
const pop = (t, a, d = 0.32) => (t < a ? 0 : eBack(prog(t, a, d)));
function rng(seed) { let s = (seed >>> 0) || 7; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 100000) / 100000; }; }
const seq = (d, n, first, base) => Math.min(base, Math.max(0.12, ((d || 9) - first - 0.3) / Math.max(1, n)));
function swing(t, a, amp = 0.22) { const u = t - a; return u < 0 ? amp : amp * Math.exp(-3.2 * u) * Math.cos(9 * u); }

// ---------- drawing helpers ----------
function rr(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
function at(x, y, s, rot, fn) { if (s <= 0.001) return; ctx.save(); ctx.translate(x, y); ctx.rotate(rot || 0); ctx.scale(s, s); fn(); ctx.restore(); }
function font(size, weight = 600, family = SANS, style = "") { ctx.font = `${style} ${weight} ${size}px ${family}`; }
function txt(s, x, y, o = {}) {
  font(o.size || 40, o.weight || 600, o.family || SANS, o.style || "");
  ctx.letterSpacing = (o.ls || 0) + "px";
  ctx.fillStyle = o.color || C.ink; ctx.textAlign = o.align || "left"; ctx.textBaseline = o.base || "alphabetic";
  ctx.fillText(s, x, y);
  ctx.letterSpacing = "0px";
}
function mono(s, x, y, o = {}) { txt(s, x, y, { family: MONO, weight: o.weight || 400, size: o.size || 26, color: o.color || C.gray, align: o.align, ls: o.ls ?? 1, base: o.base }); }
function fitSize(s, maxW, size, weight = 700, family = SANS) {
  for (; size > 14; size -= 2) { font(size, weight, family); if (ctx.measureText(s).width <= maxW) break; }
  return size;
}
function card(x, y, w, h, o = {}) {
  const r = o.r ?? 22, sh = o.shadow ?? 12;
  if (sh) { rr(x + sh, y + sh, w, h, r); ctx.fillStyle = DOTS; ctx.fill(); }
  rr(x, y, w, h, r); ctx.fillStyle = o.fill || C.white; ctx.fill();
  if (o.stroke !== false) { ctx.lineWidth = o.lw || 5; ctx.strokeStyle = o.stroke || C.ink; ctx.stroke(); }
}
function line(x1, y1, x2, y2, w = 5, c = C.ink, cap = "round") { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.lineWidth = w; ctx.strokeStyle = c; ctx.lineCap = cap; ctx.stroke(); }
function circle(x, y, r, fill, stroke = C.ink, lw = 5) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke) { ctx.lineWidth = lw; ctx.strokeStyle = stroke; ctx.stroke(); } }
function pill(x, y, s, o = {}) {
  const size = o.size || 38; font(size, 700, o.family || SANS);
  const w = Math.min(o.maxW || 900, ctx.measureText(s).width + size * 1.4), h = size * 1.9;
  const fs = fitSize(s, w - size * 1.2, size, 700, o.family || SANS);
  card(x - w / 2, y - h / 2, w, h, { r: h / 2, fill: o.fill || C.ink, shadow: o.shadow ?? 8, lw: 4 });
  txt(s, x, y + 2, { size: fs, weight: 700, color: o.color || C.white, align: "center", base: "middle", family: o.family || SANS });
}
function check(x, y, r = 34, fill = C.coral) {
  circle(x, y, r, fill, C.ink, 4);
  ctx.beginPath(); ctx.moveTo(x - r * 0.42, y + r * 0.02); ctx.lineTo(x - r * 0.1, y + r * 0.34); ctx.lineTo(x + r * 0.45, y - r * 0.3);
  ctx.lineWidth = r * 0.2; ctx.strokeStyle = C.white; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.stroke();
}
function cross(x, y, r = 34) {
  circle(x, y, r, C.ink, C.ink, 4);
  line(x - r * 0.35, y - r * 0.35, x + r * 0.35, y + r * 0.35, r * 0.2, C.coral);
  line(x + r * 0.35, y - r * 0.35, x - r * 0.35, y + r * 0.35, r * 0.2, C.coral);
}
// a document with a folded corner, centred on (0,0)
function doc(w, h, badge = "PDF", o = {}) {
  const x = -w / 2, y = -h / 2, f = w * 0.26, sh = o.shadow ?? 12;
  const path = () => { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w - f, y); ctx.lineTo(x + w, y + f); ctx.lineTo(x + w, y + h); ctx.lineTo(x, y + h); ctx.closePath(); };
  if (sh) { ctx.save(); ctx.translate(sh, sh); path(); ctx.fillStyle = DOTS; ctx.fill(); ctx.restore(); }
  path(); ctx.fillStyle = o.fill || C.white; ctx.fill(); ctx.lineWidth = o.lw || 5; ctx.strokeStyle = C.ink; ctx.lineJoin = "round"; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + w - f, y); ctx.lineTo(x + w - f, y + f); ctx.lineTo(x + w, y + f); ctx.closePath();
  ctx.fillStyle = C.pink; ctx.fill(); ctx.stroke();
  const lw = Math.max(3, w * 0.04);
  for (let i = 0; i < 4; i++) line(x + w * 0.16, y + h * (0.3 + i * 0.1), x + w * (i === 3 ? 0.55 : 0.84), y + h * (0.3 + i * 0.1), lw, C.light);
  if (badge) {
    const bw = w * 0.66, bh = h * 0.17, bx = x + w * 0.12, by = y + h * 0.7;
    rr(bx, by, bw, bh, bh * 0.25); ctx.fillStyle = o.badgeFill || C.coral; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = C.ink; ctx.stroke();
    txt(badge, bx + bw / 2, by + bh / 2 + 2, { size: fitSize(badge, bw * 0.8, bh * 0.62, 700, MONO), family: MONO, weight: 700, color: C.white, align: "center", base: "middle" });
  }
}
function phone(w, h, draw) {
  const x = -w / 2, y = -h / 2;
  card(x, y, w, h, { r: 64, fill: C.ink, shadow: 14 });
  const ix = x + 18, iy = y + 18, iw = w - 36, ih = h - 36;
  rr(ix, iy, iw, ih, 48); ctx.fillStyle = C.white; ctx.fill();
  rr(-w * 0.14, y + 30, w * 0.28, 26, 13); ctx.fillStyle = C.ink; ctx.fill();
  ctx.save(); rr(ix, iy, iw, ih, 48); ctx.clip(); ctx.translate(ix, iy); draw(iw, ih); ctx.restore();
}
const SKIN = ["#E8B48F", "#C98B62", "#F0C9A6", "#A86F4C", "#DDA27C"], HAIR = ["#2B211D", "#5A3A26", "#1E1A1A", "#7A4E2D"], SHIRT = ["#4A6FA5", "#DE6B57", "#3E8E6E", "#8E5BA8", "#E8B64C"];
function avatar(x, y, r, i = 0, ring = true) {
  ctx.save();
  circle(x, y, r, C.pink, ring ? C.ink : null, 4);
  ctx.beginPath(); ctx.arc(x, y, r - 2, 0, Math.PI * 2); ctx.clip();
  ctx.beginPath(); ctx.ellipse(x, y + r * 1.0, r * 0.82, r * 0.55, 0, 0, Math.PI * 2); ctx.fillStyle = SHIRT[i % 5]; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = C.ink; ctx.stroke();
  circle(x, y - r * 0.08, r * 0.44, SKIN[i % 5], C.ink, 3);
  ctx.beginPath(); ctx.arc(x, y - r * 0.2, r * 0.46, Math.PI * 1.02, Math.PI * 1.98); ctx.lineTo(x + r * 0.4, y - r * 0.25); ctx.closePath(); ctx.fillStyle = HAIR[i % 4]; ctx.fill();
  circle(x - r * 0.15, y - r * 0.06, r * 0.045, C.ink, null); circle(x + r * 0.15, y - r * 0.06, r * 0.045, C.ink, null);
  ctx.beginPath(); ctx.arc(x, y + r * 0.04, r * 0.15, 0.15 * Math.PI, 0.85 * Math.PI); ctx.lineWidth = 3; ctx.strokeStyle = C.ink; ctx.stroke();
  ctx.restore();
  if (ring) circle(x, y, r, null, C.ink, 4);
}
function particles(x, y, t, a, n = 14, color = C.coral, seed = 3) {
  if (t < a || t > a + 0.7) return;
  const r = rng(seed), u = eOut(prog(t, a, 0.6));
  for (let i = 0; i < n; i++) {
    const ang = r() * Math.PI * 2, d = 80 + r() * 160;
    circle(x + Math.cos(ang) * d * u, y + Math.sin(ang) * d * u, (6 + r() * 8) * (1 - u), color, null);
  }
}
function stampImg(word) {
  if (STAMPS[word]) return STAMPS[word];
  const c = document.createElement("canvas"), x = c.getContext("2d");
  x.font = `700 150px ${SANS}`; const tw = Math.min(760, x.measureText(word).width);
  c.width = tw + 120; c.height = 250;
  x.strokeStyle = C.coral; x.lineWidth = 12; x.beginPath(); x.roundRect(14, 14, c.width - 28, c.height - 28, 18); x.stroke();
  x.lineWidth = 5; x.beginPath(); x.roundRect(34, 34, c.width - 68, c.height - 68, 10); x.stroke();
  x.fillStyle = C.coral; x.textAlign = "center"; x.textBaseline = "middle";
  let size = 150; for (; size > 40; size -= 4) { x.font = `700 ${size}px ${SANS}`; if (x.measureText(word).width <= c.width - 110) break; }
  x.fillText(word, c.width / 2, c.height / 2 + 8);
  x.globalCompositeOperation = "destination-out"; const r = rng(word.length * 31 + 7);
  for (let i = 0; i < 260; i++) { x.beginPath(); x.arc(r() * c.width, r() * c.height, 1 + r() * 4.5, 0, Math.PI * 2); x.fill(); }
  STAMPS[word] = c; return c;
}
function stamp(word, x, y, t, a, rot = -0.2) {
  if (t < a) return;
  const u = prog(t, a, 0.16), s = 2.2 - 1.2 * eOut(u), img = stampImg(word);
  ctx.save(); ctx.globalAlpha = clamp(u * 2.5); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
  ctx.drawImage(img, -img.width / 2, -img.height / 2); ctx.restore();
  particles(x, y, t, a + 0.1, 16, C.coral, word.length);
}
function arrow(x1, y1, x2, y2, u, w = 6, c = C.ink) {
  if (u <= 0) return;
  const xe = x1 + (x2 - x1) * u, ye = y1 + (y2 - y1) * u;
  line(x1, y1, xe, ye, w, c);
  if (u > 0.85) { const a = Math.atan2(y2 - y1, x2 - x1), k = 26; line(xe, ye, xe - k * Math.cos(a - 0.5), ye - k * Math.sin(a - 0.5), w, c); line(xe, ye, xe - k * Math.cos(a + 0.5), ye - k * Math.sin(a + 0.5), w, c); }
}
function parseSize(s) {
  const m = String(s || "").replace(",", ".").match(/([\d.]+)\s*(kb|mb|gb)?/i); if (!m) return null;
  const v = parseFloat(m[1]), u = (m[2] || "KB").toUpperCase();
  return u === "MB" ? v * 1000 : u === "GB" ? v * 1e6 : v;
}
const fmtSize = kb => (kb >= 1000 ? (kb / 1000).toFixed(1) + " MB" : Math.round(kb) + " KB");

// ---------- background ----------
function makeBackgrounds() {
  const mk = (bg, dot) => {
    const c = document.createElement("canvas"); c.width = W; c.height = H; const x = c.getContext("2d");
    x.fillStyle = bg; x.fillRect(0, 0, W, H); x.fillStyle = dot;
    for (let yy = 3; yy < H; yy += 7) for (let xx = (yy % 14 ? 3 : 6.5); xx < W; xx += 7) { x.beginPath(); x.arc(xx, yy, 1.05, 0, Math.PI * 2); x.fill(); }
    return c;
  };
  BG = mk(C.bg, C.dot); BGD = mk(C.dark, C.darkDot);
  const d = document.createElement("canvas"); d.width = 7; d.height = 7; const dx = d.getContext("2d");
  dx.fillStyle = C.ink; dx.beginPath(); dx.arc(3.5, 3.5, 1.7, 0, Math.PI * 2); dx.fill();
  DOTS = ctx.createPattern(d, "repeat");
}
const CROSSES = (() => { const r = rng(11), out = []; for (let i = 0; i < 46; i++) out.push([r() * W, r() * H, 9 + r() * 9, r() * 6.28]); return out; })();
function background(t, dark) {
  ctx.drawImage(dark ? BGD : BG, 0, 0);
  ctx.strokeStyle = dark ? "#3a3236" : "rgba(222,107,87,0.42)"; ctx.lineWidth = 3; ctx.lineCap = "round";
  for (const [x, y, s, ph] of CROSSES) {
    const yy = (y - t * 14 + H) % H, xx = x + Math.sin(t * 0.8 + ph) * 6;
    ctx.beginPath(); ctx.moveTo(xx - s, yy - s); ctx.lineTo(xx + s, yy + s); ctx.moveTo(xx + s, yy - s); ctx.lineTo(xx - s, yy + s); ctx.stroke();
  }
}

// ---------- headline: builds word by word, accent words in italic serif coral ----------
const SANS_SIZE = 70, SERIF_SIZE = 86, LINE = 88, LEFT = 72, MAXW = 936, TOP = 230;
function layoutShot(i) {
  if (LAYOUT[i]) return LAYOUT[i];
  const sh = REEL.shots[i];
  const acc = new Set((sh.accent || []).flatMap(a => String(a).split(/\s+/)).map(w => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "")).filter(Boolean));
  const words = sh.words.map(w => {
    const key = w.w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
    const isAcc = acc.has(key) || /^\d/.test(key);
    font(isAcc ? SERIF_SIZE : SANS_SIZE, isAcc ? 400 : 600, isAcc ? SERIF : SANS, isAcc ? "italic" : "");
    return { ...w, acc: isAcc, width: ctx.measureText(w.w).width };
  });
  font(SANS_SIZE, 600); const space = ctx.measureText(" ").width;
  let x = 0, ln = 0;
  for (const w of words) { if (x > 0 && x + w.width > MAXW) { x = 0; ln++; } w.x = x; w.line = ln; x += w.width + space; }
  return (LAYOUT[i] = { words, lines: ln + 1 });
}
function headline(i, t, dark) {
  const L = layoutShot(i); let last = 0;
  L.words.forEach((w, k) => { if (t >= w.t0 - 0.03) last = k; });
  const page = Math.floor(L.words[last].line / 3);
  for (const w of L.words) {
    if (Math.floor(w.line / 3) !== page || t < w.t0 - 0.03) continue;
    const u = eOut(prog(t, w.t0 - 0.03, 0.14)), y = TOP + (w.line % 3) * LINE + (1 - u) * 16;
    ctx.globalAlpha = u;
    if (w.acc) txt(w.w, LEFT + w.x, y + 4, { size: SERIF_SIZE, weight: 400, family: SERIF, style: "italic", color: C.coral });
    else txt(w.w, LEFT + w.x, y, { size: SANS_SIZE, weight: 600, color: dark ? "#F3EEE7" : C.ink });
    ctx.globalAlpha = 1;
  }
}
function header(sh, t, dark) {
  mono("// " + (sh.tag || REEL.tag || "ilovedocuments"), LEFT, 104, { size: 27, color: dark ? "#8f8589" : C.gray });
  const m = sh.meter || {};
  if (m.label || m.value) {
    font(27, 700, MONO); const vw = ctx.measureText(String(m.value || "")).width;
    mono(String(m.value || ""), W - LEFT, 104, { size: 27, weight: 700, color: C.coral, align: "right" });
    mono(String(m.label || "") + " ", W - LEFT - vw - 6, 104, { size: 27, color: dark ? "#8f8589" : C.gray, align: "right" });
  }
}

// ---------- scenes (local time t from the shot start, d = shot length, p = params) ----------
const S = {};
S.phone_upload = {
  hits: p => [0.6],
  draw(t, p) {
    const err = p.state !== "success";
    at(540, 1120, pop(t, 0), 0, () => phone(460, 880, (sw, sh) => {
      mono("// upload", 40, 86, { size: 24 });
      txt(p.title || "Application form", 40, 150, { size: fitSize(p.title || "Application form", sw - 80, 42), weight: 700 });
      mono("Document", 40, 230, { size: 22 });
      at(sw / 2, 320, pop(t, 0.2), 0, () => {
        card(-sw / 2 + 34, -62, sw - 68, 124, { r: 20, shadow: 6, lw: 4, stroke: t > 0.6 ? (err ? C.coral : C.ink) : C.ink });
        at(-sw / 2 + 92, 0, 1, 0, () => doc(56, 72, "", { shadow: 0, lw: 4 }));
        const fn = p.file || "document.pdf";
        txt(fn, -sw / 2 + 140, -6, { size: fitSize(fn, sw - 230, 30, 600), weight: 600 });
        mono(p.size || "", -sw / 2 + 140, 34, { size: 24, color: err && t > 0.6 ? C.coral : C.gray, weight: 700 });
      });
      for (let i = 0; i < 3; i++) { rr(40, 430 + i * 70, sw - 80 - i * 90, 26, 13); ctx.fillStyle = C.light; ctx.fill(); }
      rr(40, sh - 170, sw - 80, 96, 48); ctx.fillStyle = t > 0.6 && !err ? C.ink : C.coral; ctx.fill();
      txt(t > 0.6 && !err ? "Submitted" : "Submit", sw / 2, sh - 122, { size: 38, weight: 700, color: C.white, align: "center", base: "middle" });
    }));
    const u = pop(t, 0.6);
    at(540, 610, u, err ? -0.05 : 0.04, () => pill(0, 0, (err ? "X  " : "") + (p.text || (err ? "File too large" : "Uploaded")), { fill: err ? C.coral : C.ink, size: 40, maxW: 900 }));
    at(760, 790, pop(t, 0.7), 0, () => (err ? cross(0, 0, 46) : check(0, 0, 46)));
  },
};
S.file_shrink = {
  hits: p => [1.45],
  draw(t, p) {
    const a = parseSize(p.from) ?? 2400, b = parseSize(p.to) ?? 180, u = eInOut(prog(t, 0.45, 0.95)), kb = a + (b - a) * u;
    const sq = Math.sin(Math.PI * u);
    at(540, 1010, pop(t, 0), 0, () => { ctx.save(); ctx.scale(1 - 0.16 * sq - 0.1 * u, 1 - 0.1 * sq - 0.06 * u); doc(380, 480, (p.file || "PDF").split(".").pop().toUpperCase().slice(0, 4)); ctx.restore(); });
    if (t > 0.45 && t < 1.45) { const k = Math.sin(t * 30) * 8; arrow(150 + k, 1010, 290 + k + 40 * sq, 1010, 1, 8, C.coral); arrow(930 - k, 1010, 790 - k - 40 * sq, 1010, 1, 8, C.coral); }
    at(540, 1390, pop(t, 0.15), 0, () => pill(0, 0, fmtSize(kb), { fill: u >= 1 ? C.coral : C.ink, size: 64 }));
    mono((p.file || "your file").toLowerCase(), 540, 1500, { size: 28, align: "center" });
    at(735, 790, pop(t, 1.45), 0, () => check(0, 0, 50));
    particles(540, 1010, t, 1.45, 12, C.coral, 5);
  },
};
S.stamp = {
  hits: p => [0.62],
  draw(t, p) {
    at(540, 1000, pop(t, 0), -0.04, () => {
      card(-340, -270, 680, 540, { r: 28 });
      circle(-285, -215, 15, C.bg, C.ink, 4);
      mono("// " + (p.label || "price"), -285, -150, { size: 28 });
      const on = p.on || "Rs 50 / page";
      txt(on, 0, -50, { size: fitSize(on, 600, 96), weight: 700, align: "center", base: "middle" });
      if (p.sub) mono(p.sub, 0, 30, { size: 28, align: "center" });
      for (let k = 0; k < 3; k++) line(-260, 110 + k * 46, 260 - k * 120, 110 + k * 46, 8, C.light);
    });
    stamp((p.word || "FREE").toUpperCase(), 600, 1200, t, 0.5, -0.16);
  },
};
S.counter = {
  hits: p => [1.0],
  draw(t, p) {
    const v = Number(p.value) || 45, n = Math.round(v * eOut(prog(t, 0.08, 0.9)));
    const g = ctx.createRadialGradient(540, 1100, 20, 540, 1100, 330); g.addColorStop(0, "rgba(222,107,87,0.28)"); g.addColorStop(1, "rgba(222,107,87,0)");
    ctx.fillStyle = g; ctx.fillRect(140, 700, 800, 800);
    at(540, 1130, 0.9 + 0.1 * pop(t, 0), 0, () => txt(String(n), 0, 0, { size: fitSize(String(v), 760, 330, 700), weight: 700, color: C.coral, align: "center", base: "middle" }));
    mono((p.label || "FREE TOOLS").toUpperCase(), 540, 1340, { size: 40, color: C.ink, align: "center", ls: 6, weight: 700 });
    if (p.badge) at(800, 860, pop(t, 0.85), -0.14, () => {
      font(46, 700); const bw = ctx.measureText(p.badge).width + 110;
      card(-bw / 2, -50, bw, 100, { r: 22, fill: C.ink, shadow: 10 });
      for (let i = 0; i < 4; i++) line(-bw / 2 + 40 + i * 30, -50, -bw / 2 + 40 + i * 30, -68, 5);
      txt(p.badge, -14, 4, { size: 46, weight: 700, color: C.white, align: "center", base: "middle" });
      txt("*", bw / 2 - 34, 14, { size: 64, weight: 700, color: C.coral, align: "center", base: "middle" });
    });
  },
};
S.tool_grid = {
  hits: p => [0.95],
  draw(t, p) {
    const cols = 5, rows = 5, tw = 120, th = 150, gx = 44, gy = 36, x0 = 540 - (cols * tw + (cols - 1) * gx) / 2 + tw / 2, y0 = 640;
    const labels = ["PDF", "JPG", "DOC", "XLS", "PNG", "KB", "SIGN", "ZIP"], r = rng(4);
    mono((p.count ? p.count + " FREE TOOLS" : "FREE TOOLS"), 540, 560, { size: 30, color: C.ink, align: "center", weight: 700, ls: 4 });
    for (let i = 0; i < cols * rows; i++) {
      const c = i % cols, rw = Math.floor(i / cols), s = pop(t, 0.03 * i, 0.25) * (t > 0.95 ? 0.85 : 1);
      const lab = labels[Math.floor(r() * labels.length)], fill = r() > 0.6 ? C.ink : C.coral;
      ctx.globalAlpha = t > 0.95 ? 0.45 : 1;
      at(x0 + c * (tw + gx), y0 + rw * (th + gy) + th / 2, s, 0, () => doc(tw, th, lab, { shadow: 6, lw: 4, badgeFill: fill }));
      ctx.globalAlpha = 1;
    }
    at(540, 1130, pop(t, 0.95), -0.03, () => {
      const hl = p.highlight || "Compress PDF";
      card(-380, -150, 760, 300, { r: 30 });
      at(-250, 0, 1, 0, () => doc(150, 190, hl.split(" ").pop().toUpperCase().slice(0, 4), { shadow: 6 }));
      txt(hl, -140, -14, { size: fitSize(hl, 470, 64), weight: 700 });
      mono("free · no sign-up", -140, 50, { size: 28, color: C.coral, weight: 700 });
    });
  },
};
S.steps = {
  hits: (p, d) => (p.items || [1, 2, 3]).slice(0, 3).map((_, i, a) => 0.15 + i * seq(d, a.length, 0.15, 0.5)),
  draw(t, p, d) {
    const items = (p.items || ["Upload", "Choose size", "Download"]).slice(0, 3), xs = [210, 540, 870], gap = seq(d, items.length, 0.15, 0.5);
    items.forEach((it, i) => {
      const a = 0.15 + i * gap, x = xs[i], top = 470;
      if (t < a) { ctx.setLineDash([14, 12]); rr(x - 135, 760, 270, 440, 22); ctx.lineWidth = 4; ctx.strokeStyle = "rgba(30,26,26,0.25)"; ctx.stroke(); ctx.setLineDash([]); txt("0" + (i + 1), x, 1000, { size: 90, weight: 700, color: "rgba(30,26,26,0.12)", align: "center", base: "middle" }); return; }
      const drop = (1 - eOut(prog(t, a, 0.35))) * -420, ang = swing(t, a + 0.2, 0.18);
      ctx.save(); ctx.translate(x, top + drop); ctx.rotate(ang);
      line(0, -60, 0, 270, 4); circle(0, 270, 12, C.coral, C.ink, 4);
      card(-135, 290, 270, 440, { r: 22 });
      rr(-135, 290, 270, 90, [22, 22, 0, 0]); ctx.fillStyle = i === items.length - 1 ? C.coral : C.ink; ctx.fill();
      txt(it.toUpperCase(), 0, 337, { size: fitSize(it.toUpperCase(), 230, 34, 700), weight: 700, color: C.white, align: "center", base: "middle" });
      txt("0" + (i + 1), 0, 520, { size: 110, weight: 700, color: C.coral, align: "center", base: "middle" });
      for (let k = 0; k < 3; k++) line(-90, 610 + k * 34, 90 - k * 40, 610 + k * 34, 6, C.light);
      ctx.restore();
    });
  },
};
S.browser = {
  hits: p => [1.3],
  draw(t, p) {
    const url = p.url || "ilovedocuments.ai", btn = p.button || "Compress PDF";
    at(540, 1100, pop(t, 0), 0, () => {
      card(-430, -460, 860, 920, { r: 30 });
      rr(-430, -460, 860, 110, [30, 30, 0, 0]); ctx.fillStyle = C.light; ctx.fill(); line(-430, -350, 430, -350, 5);
      [0, 1, 2].forEach(i => circle(-380 + i * 42, -405, 12, i ? C.white : C.coral, C.ink, 3));
      card(-230, -436, 620, 62, { r: 31, shadow: 0, lw: 4 });
      const n = Math.floor(url.length * prog(t, 0.15, 0.7)), shown = url.slice(0, n);
      mono(shown + (Math.floor(t * 4) % 2 && n < url.length ? "|" : ""), -200, -395, { size: 30, color: C.ink, weight: 700 });
      txt("ilovedocuments", -10, -200, { size: 66, weight: 700, align: "center" });
      txt(".ai", 245, -196, { size: 76, family: SERIF, style: "italic", weight: 400, color: C.coral, align: "left" });
      mono("every PDF & image tool, free", 0, -130, { size: 28, align: "center" });
      const press = t > 1.3 && t < 1.45 ? 0.94 : 1;
      at(0, 60, pop(t, 0.75) * press, 0, () => { card(-300, -80, 600, 160, { r: 80, fill: C.coral, shadow: 10 }); txt(btn, 0, 4, { size: fitSize(btn, 520, 60), weight: 700, color: C.white, align: "center", base: "middle" }); });
      for (let k = 0; k < 3; k++) { rr(-330, 220 + k * 64, 660 - k * 120, 30, 15); ctx.fillStyle = C.light; ctx.fill(); }
    });
    if (t > 0.85) {
      const u = eInOut(prog(t, 0.85, 0.42)), cx = 860 + (620 - 860) * u, cy = 1560 + (1180 - 1560) * u;
      if (t > 1.3) { const r = 30 + 90 * prog(t, 1.3, 0.4); circle(620, 1170, r, null, `rgba(222,107,87,${1 - prog(t, 1.3, 0.4)})`, 6); }
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx, cy + 74); ctx.lineTo(cx + 20, cy + 56); ctx.lineTo(cx + 36, cy + 88); ctx.lineTo(cx + 48, cy + 82); ctx.lineTo(cx + 32, cy + 50); ctx.lineTo(cx + 56, cy + 50); ctx.closePath();
      ctx.fillStyle = C.white; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.lineJoin = "round"; ctx.stroke();
    }
  },
};
S.before_after = {
  hits: p => [0.35, 0.95],
  draw(t, p) {
    at(290, 1050, pop(t, 0), -0.06, () => { doc(330, 420, "", {}); txt(p.before || "2.4 MB", 0, 20, { size: fitSize(p.before || "2.4 MB", 270, 64), weight: 700, align: "center", base: "middle" }); });
    at(290, 1370, pop(t, 0.35), -0.06, () => pill(0, 0, "X  " + (p.before_label || "REJECTED"), { fill: C.coral, size: 34, maxW: 420 }));
    arrow(470, 1050, 610, 1050, eOut(prog(t, 0.5, 0.3)), 8, C.ink);
    at(790, 1040, pop(t, 0.7), 0.05, () => { doc(330, 420, "", {}); txt(p.after || "180 KB", 0, 20, { size: fitSize(p.after || "180 KB", 270, 64), weight: 700, color: C.coral, align: "center", base: "middle" }); });
    at(790, 1360, pop(t, 0.95), 0.05, () => pill(0, 0, p.after_label || "ACCEPTED", { fill: C.ink, size: 34, maxW: 420 }));
    at(925, 820, pop(t, 0.95), 0, () => check(0, 0, 44));
  },
};
S.cyber_cafe = {
  hits: p => [1.0],
  draw(t, p) {
    at(470, 1120, pop(t, 0), 0, () => {
      card(-300, -260, 600, 560, { r: 10 });
      for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(-300 + i * 100, -260); ctx.lineTo(-300 + (i + 1) * 100, -260); ctx.lineTo(-300 + (i + 1) * 100, -190); ctx.arc(-250 + i * 100, -190, 50, 0, Math.PI); ctx.closePath(); ctx.fillStyle = i % 2 ? C.white : C.coral; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = C.ink; ctx.stroke(); }
      card(-250, -400, 500, 120, { r: 16, fill: C.ink, shadow: 8 });
      txt("CYBER CAFE", 0, -338, { size: 58, weight: 700, color: "#F7C9BE", align: "center", base: "middle", ls: 3 });
      card(-240, -90, 230, 180, { r: 12, fill: C.pink, shadow: 0, lw: 4 }); rr(-205, -60, 160, 100, 8); ctx.fillStyle = C.ink; ctx.fill();
      card(40, -90, 200, 390, { r: 12, fill: C.light, shadow: 0, lw: 4 }); circle(200, 110, 9, C.ink, null);
    });
    const a = swing(t, 0.25, 0.16);
    ctx.save(); ctx.translate(820, 760); ctx.rotate(a);
    line(0, 0, 0, 120, 4); card(-120, 120, 240, 300, { r: 20, fill: C.white });
    circle(0, 150, 12, C.bg, C.ink, 4);
    const pr = p.price || "Rs 50";
    txt(pr, 0, 260, { size: fitSize(pr, 200, 74), weight: 700, align: "center", base: "middle" });
    mono(p.text || "per page", 0, 330, { size: 24, align: "center" });
    if (t > 0.75) line(-110, 300, -110 + 220 * eOut(prog(t, 0.75, 0.2)), 220, 12, C.coral);
    ctx.restore();
    at(820, 1260, pop(t, 1.0), -0.1, () => pill(0, 0, p.free || "FREE", { fill: C.coral, size: 56 }));
  },
};
S.privacy = {
  hits: p => [0.8],
  draw(t, p) {
    at(540, 1110, pop(t, 0), 0, () => phone(460, 860, (sw, sh) => {
      mono("// your phone", 40, 86, { size: 24 });
      const cx = sw / 2, cy = sh / 2 - 20, s = pop(t, 0.2);
      at(cx, cy, s, 0, () => {
        ctx.beginPath(); ctx.moveTo(0, -150); ctx.lineTo(125, -100); ctx.lineTo(115, 40); ctx.quadraticCurveTo(80, 130, 0, 170); ctx.quadraticCurveTo(-80, 130, -115, 40); ctx.lineTo(-125, -100); ctx.closePath();
        ctx.fillStyle = C.coral; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.stroke();
        card(-48, -10, 96, 80, { r: 12, fill: C.ink, shadow: 0, stroke: false });
        ctx.beginPath(); ctx.arc(0, -10, 32, Math.PI, 0); ctx.lineWidth = 12; ctx.strokeStyle = C.ink; ctx.stroke();
      });
      for (let i = 0; i < 3; i++) { const ang = t * 1.6 + i * 2.09; at(cx + Math.cos(ang) * 175, cy + Math.sin(ang) * 220, pop(t, 0.3 + i * 0.1) * 0.9, 0, () => doc(70, 90, ["PDF", "JPG", "DOC"][i], { shadow: 0, lw: 4 })); }
    }));
    at(820, 690, pop(t, 0.5), 0.08, () => {
      ctx.beginPath(); ctx.arc(-40, 10, 50, Math.PI * 0.6, Math.PI * 1.8); ctx.arc(30, -10, 60, Math.PI * 1.1, Math.PI * 0.2); ctx.closePath();
      ctx.fillStyle = C.white; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke(); line(-90, 70, 100, -70, 10, C.coral);
    });
    at(540, 1630, pop(t, 0.8), -0.03, () => pill(0, 0, p.text || "Never uploaded", { fill: C.ink, size: 40 }));
  },
};
S.deadline = {
  hits: p => [0.55],
  draw(t, p) {
    const sh = t > 0.55 && t < 0.95 ? Math.sin(t * 70) * 0.05 : 0;
    at(540, 1010, pop(t, 0), sh, () => {
      circle(0, 0, 250, C.white, C.ink, 7); circle(14, 14, 250, null, null);
      for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; line(Math.cos(a) * 205, Math.sin(a) * 205, Math.cos(a) * 230, Math.sin(a) * 230, i % 3 ? 4 : 8); }
      const tm = (p.time || "11:59").match(/(\d+):(\d+)/) || [0, 11, 59], hh = +tm[1] % 12, mm = +tm[2];
      const u = eOut(prog(t, 0.05, 0.7)), ma = (mm / 60) * 2 * Math.PI * u - Math.PI / 2 - 2 * Math.PI * (1 - u), ha = ((hh + mm / 60) / 12) * 2 * Math.PI - Math.PI / 2;
      line(0, 0, Math.cos(ha) * 120, Math.sin(ha) * 120, 14); line(0, 0, Math.cos(ma) * 185, Math.sin(ma) * 185, 9, C.coral); circle(0, 0, 16, C.ink, null);
      [-1, 1].forEach(s => { ctx.beginPath(); ctx.arc(s * 170, -230, 60, Math.PI, 0); ctx.closePath(); ctx.fillStyle = C.coral; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.stroke(); });
    });
    at(540, 1400, pop(t, 0.4), 0, () => pill(0, 0, p.time || "11:59 PM", { fill: C.coral, size: 70 }));
    at(780, 640, pop(t, 0.6), 0.08, () => { card(-170, -90, 340, 180, { r: 18 }); rr(-170, -90, 340, 56, [18, 18, 0, 0]); ctx.fillStyle = C.ink; ctx.fill(); mono("LAST DATE", 0, -55, { size: 26, color: C.white, align: "center", weight: 700 }); const s = p.text || "TODAY"; txt(s, 0, 38, { size: fitSize(s, 300, 54), weight: 700, color: C.coral, align: "center", base: "middle" }); });
  },
};
S.id_card = {
  hits: p => [0.35],
  draw(t, p) {
    const drop = (1 - eOut(prog(t, 0, 0.4))) * -600, ang = swing(t, 0.35, 0.12);
    ctx.save(); ctx.translate(540, 470 + drop); ctx.rotate(ang);
    line(-90, -90, -18, 200, 14, C.coral); line(90, -90, 18, 200, 14, C.coral);
    rr(-34, 196, 68, 40, 8); ctx.fillStyle = C.gray; ctx.fill();
    card(-230, 236, 460, 640, { r: 28 });
    rr(-230, 236, 460, 90, [28, 28, 0, 0]); ctx.fillStyle = C.ink; ctx.fill();
    const title = "ID · " + (p.title || "CARD").toUpperCase();
    mono(title, 0, 292, { size: fitSize(title, 400, 30, 700, MONO), color: C.white, align: "center", weight: 700, ls: 3 });
    avatar(0, 480, 120, p.look || 1);
    circle(0, 480, 128, null, C.coral, 6);
    const name = (p.name || "YOUR NAME").toUpperCase();
    txt(name, 0, 690, { size: fitSize(name, 400, 50), weight: 700, align: "center" });
    mono("// " + (p.sub || "photo 35 x 45 mm"), 0, 740, { size: 24, align: "center" });
    for (let i = 0; i < 16; i++) { rr(-170 + i * 22, 780, i % 3 ? 10 : 16, 60, 2); ctx.fillStyle = C.ink; ctx.fill(); }
    ctx.restore();
  },
};
S.spotlight = {
  dark: true,
  hits: p => [0.6],
  draw(t, p) {
    const u = eOut(prog(t, 0.05, 0.4));
    const g = ctx.createLinearGradient(0, 380, 0, 1500); g.addColorStop(0, `rgba(255,248,240,${0.05 + 0.16 * u})`); g.addColorStop(1, `rgba(255,248,240,${0.02 + 0.08 * u})`);
    ctx.beginPath(); ctx.moveTo(470, 380); ctx.lineTo(610, 380); ctx.lineTo(900, 1480); ctx.lineTo(180, 1480); ctx.closePath(); ctx.fillStyle = g; ctx.fill();
    const r = rng(9); for (let i = 0; i < 26; i++) { const x = 300 + r() * 480, y = 500 + ((r() * 900 + t * 30) % 900); circle(x, y, 2 + r() * 2, `rgba(255,255,255,${0.35 * u})`, null); }
    ctx.beginPath(); ctx.ellipse(540, 1490, 380, 40, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,0.35)"; ctx.fill();
    rr(220, 1270, 640, 30, 8); ctx.fillStyle = C.coral; ctx.fill();
    rr(250, 1300, 580, 230, 10); ctx.fillStyle = C.wood; ctx.fill();
    rr(300, 1350, 160, 50, 8); ctx.fillStyle = "#4b372e"; ctx.fill(); rr(620, 1350, 160, 50, 8); ctx.fill();
    circle(380, 1375, 6, C.gold, null); circle(700, 1375, 6, C.gold, null);
    const title = (p.title || "BOSS").toUpperCase();
    at(540, 1190, pop(t, 0.3), 0, () => {
      font(92, 700); const tw = Math.max(320, ctx.measureText(title).width + 90);
      rr(-tw / 2, -70, tw, 140, 14); ctx.fillStyle = C.gold; ctx.fill(); rr(-tw / 2 + 14, -56, tw - 28, 112, 8); ctx.fillStyle = "#120f10"; ctx.fill();
      const n = Math.floor(title.length * prog(t, 0.45, 0.5));
      txt(title.slice(0, n), 0, 6, { size: fitSize(title, tw - 70, 92), weight: 700, color: C.gold, align: "center", base: "middle", ls: 6 });
    });
    at(540, 1050, pop(t, 0.95), 0, () => {
      ctx.beginPath(); ctx.moveTo(-110, 50); ctx.lineTo(-120, -50); ctx.lineTo(-55, 0); ctx.lineTo(0, -70); ctx.lineTo(55, 0); ctx.lineTo(120, -50); ctx.lineTo(110, 50); ctx.closePath();
      ctx.fillStyle = C.gold; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = "#120f10"; ctx.stroke();
    });
  },
};
S.cta = {
  hits: p => [0.85],
  wipe: true,
  draw(t, p) {
    const kw = (p.keyword || "SAVE").toUpperCase();
    at(540, 760, pop(t, 0.35), -0.03, () => {
      txt(kw, 0, 0, { size: fitSize(kw, 800, 170), weight: 700, color: C.coral, align: "center", base: "middle" });
      font(fitSize(kw, 800, 170), 700); const w = ctx.measureText(kw).width;
      line(-w / 2, 90, w / 2, 90, 10, C.ink);
    });
    at(540, 1100, pop(t, 0.55), 0, () => {
      card(-400, -110, 800, 220, { r: 30 });
      mono("// your next form", -350, -50, { size: 26 });
      const fill = t > 0.85 ? C.coral : C.white;
      ["heart", "chat", "send", "save"].forEach((k, i) => {
        const x = -300 + i * 170, y = 30;
        if (k === "heart") { ctx.beginPath(); ctx.moveTo(x, y + 30); ctx.bezierCurveTo(x - 60, y - 10, x - 30, y - 50, x, y - 20); ctx.bezierCurveTo(x + 30, y - 50, x + 60, y - 10, x, y + 30); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.stroke(); }
        if (k === "chat") { circle(x, y, 32, null, C.ink, 6); }
        if (k === "send") { ctx.beginPath(); ctx.moveTo(x - 34, y - 26); ctx.lineTo(x + 36, y - 30); ctx.lineTo(x - 6, y + 34); ctx.closePath(); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.lineJoin = "round"; ctx.stroke(); }
        if (k === "save") {
          const s = t > 0.85 && t < 1.05 ? 1.25 : 1;
          at(x + 50, y, s, 0, () => { ctx.beginPath(); ctx.moveTo(-26, -38); ctx.lineTo(26, -38); ctx.lineTo(26, 38); ctx.lineTo(0, 16); ctx.lineTo(-26, 38); ctx.closePath(); ctx.fillStyle = fill; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.lineJoin = "round"; ctx.stroke(); });
        }
      });
    });
    particles(690, 1130, t, 0.85, 12, C.coral, 8);
    at(540, 1420, pop(t, 1.0), 0, () => pill(0, 0, REEL.url || "ilovedocuments.ai", { fill: C.ink, size: 52 }));
    if (p.line) mono(p.line, 540, 1530, { size: 28, align: "center" });
  },
};
S.split_flap = {
  hits: p => [0.2 + Math.min(12, (p.word || "").length) * 0.07],
  draw(t, p) {
    const word = (p.word || "ILOVEDOCS").toUpperCase().slice(0, 12), n = word.length;
    const tw = Math.min(110, 820 / n), th = tw * 1.45, x0 = 540 - (n * tw + (n - 1) * 10) / 2;
    at(540, 1040, pop(t, 0), 0, () => {
      line(-300, -th / 2 - 60, -300, -th / 2 - 260, 4); line(300, -th / 2 - 60, 300, -th / 2 - 260, 4);
      card(-(n * (tw + 10)) / 2 - 50, -th / 2 - 60, n * (tw + 10) + 90, th + 120, { r: 24, fill: C.ink, shadow: 12 });
    });
    const r = rng(Math.floor(t * 20) + 3), AZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    for (let i = 0; i < n; i++) {
      if (t < 0.12) break;
      const x = x0 + i * (tw + 10), y = 1040 - th / 2, done = t > 0.2 + i * 0.07;
      rr(x, y, tw, th, 8); ctx.fillStyle = "#2b2627"; ctx.fill();
      const ch = done ? word[i] : AZ[Math.floor(r() * AZ.length)];
      txt(ch, x + tw / 2, y + th / 2 + 4, { size: tw * 0.9, weight: 700, color: done ? C.white : "#9a8f8a", align: "center", base: "middle" });
      line(x, y + th / 2, x + tw, y + th / 2, 3, "#120f10", "butt");
    }
    if (p.sub) at(540, 1320, pop(t, 0.9), 0, () => pill(0, 0, p.sub, { fill: C.coral, size: 40 }));
  },
};
S.convert = {
  hits: p => [0.85],
  draw(t, p) {
    const from = (p.from || "PDF").toUpperCase().slice(0, 5), to = (p.to || "WORD").toUpperCase().slice(0, 5);
    at(280, 1060, pop(t, 0), -0.05, () => doc(300, 390, from, {}));
    arrow(450, 1060, 620, 1060, eOut(prog(t, 0.3, 0.3)), 9, C.coral);
    if (t > 0.45 && t < 0.85) { const u = eInOut(prog(t, 0.45, 0.4)); at(280 + 520 * u, 1060 - Math.sin(Math.PI * u) * 160, 0.6, u * 0.4, () => doc(300, 390, from, { shadow: 0 })); }
    ctx.setLineDash([16, 12]); rr(650, 865, 300, 390, 10); ctx.lineWidth = 4; ctx.strokeStyle = "rgba(30,26,26,0.3)"; ctx.stroke(); ctx.setLineDash([]);
    at(800, 1060, pop(t, 0.85), 0.04, () => doc(300, 390, to, { badgeFill: C.ink }));
    at(930, 860, pop(t, 1.0), 0, () => check(0, 0, 44));
    if (p.text) at(540, 1440, pop(t, 1.05), 0, () => pill(0, 0, p.text, { fill: C.ink, size: 40 }));
  },
};
S.photo_cutout = {
  hits: p => [1.15],
  draw(t, p) {
    const x = 270, y = 700, w = 540, h = 680, u = eInOut(prog(t, 0.3, 0.8)), cutY = y + h * u;
    at(540, 1040, pop(t, 0), 0, () => card(-w / 2, -h / 2, w, h, { r: 26 }));
    if (t > 0.05) {
      ctx.save(); rr(x, y, w, h, 26); ctx.clip();
      for (let yy = y; yy < y + h; yy += 40) for (let xx = x; xx < x + w; xx += 40) { ctx.fillStyle = ((xx - x + yy - y) / 40) % 2 ? "#ffffff" : "#e9e4de"; ctx.fillRect(xx, yy, 40, 40); }
      ctx.beginPath(); ctx.rect(x, cutY, w, y + h - cutY); ctx.clip();
      ctx.fillStyle = C.pink; ctx.fillRect(x, y, w, h);
      for (let k = -h; k < w; k += 46) line(x + k, y + h, x + k + h, y, 14, "rgba(222,107,87,0.35)", "butt");
      ctx.restore();
      ctx.save(); rr(x, y, w, h, 26); ctx.clip();
      ctx.beginPath(); ctx.ellipse(540, y + h - 10, 210, 170, 0, Math.PI, 0); ctx.fillStyle = SHIRT[0]; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke();
      circle(540, y + 300, 120, SKIN[0], C.ink, 5);
      ctx.beginPath(); ctx.arc(540, y + 270, 126, Math.PI * 1.02, Math.PI * 1.98); ctx.closePath(); ctx.fillStyle = HAIR[0]; ctx.fill();
      circle(500, y + 310, 8, C.ink, null); circle(580, y + 310, 8, C.ink, null);
      ctx.beginPath(); ctx.arc(540, y + 335, 34, 0.15 * Math.PI, 0.85 * Math.PI); ctx.lineWidth = 5; ctx.stroke();
      ctx.restore();
      rr(x, y, w, h, 26); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke();
      if (t > 0.3 && t < 1.12) line(x - 20, cutY, x + w + 20, cutY, 8, C.coral);
    }
    at(810, 720, pop(t, 1.15), 0, () => check(0, 0, 48));
    at(540, 1520, pop(t, 1.2), -0.03, () => pill(0, 0, p.text || "Background removed", { fill: C.ink, size: 40 }));
  },
};
// ---------- general scenes, for stories that are not about a document ----------
function wrapLines(s, maxW, size, weight = 600, family = SANS) {
  font(size, weight, family); const out = []; let cur = "";
  for (const w of String(s).split(/\s+/)) { const t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; }
  if (cur) out.push(cur); return out;
}
function para(s, x, y, maxW, size, o = {}) {
  const lines = wrapLines(s, maxW, size, o.weight || 600, o.family || SANS).slice(0, o.max || 4);
  lines.forEach((l, i) => txt(l, x, y + i * size * 1.22, { size, weight: o.weight || 600, family: o.family || SANS, color: o.color || C.ink, align: o.align || "left", style: o.style || "" }));
  return lines.length;
}
S.news = {
  hits: p => [0.5],
  draw(t, p) {
    at(540, 1060, pop(t, 0), -0.03, () => {
      card(-420, -360, 840, 720, { r: 18 });
      rr(-420, -360, 840, 110, [18, 18, 0, 0]); ctx.fillStyle = C.ink; ctx.fill();
      txt((p.source || "THE DAILY NEWS").toUpperCase(), 0, -300, { size: fitSize((p.source || "THE DAILY NEWS").toUpperCase(), 700, 46, 700, SERIF), family: SERIF, weight: 400, color: C.white, align: "center", base: "middle" });
      mono(p.date || "today", -370, -200, { size: 24 });
      const h = p.headline || "A free tool everyone should know about";
      para(h, -370, -120, 740, 56, { weight: 700, max: 4 });
      for (let k = 0; k < 4; k++) line(-370, 170 + k * 42, 370 - (k % 2) * 160, 170 + k * 42, 9, C.light);
    });
    at(760, 650, pop(t, 0.5), 0.12, () => pill(0, 0, (p.tag || "NEW").toUpperCase(), { fill: C.coral, size: 44 }));
  },
};
S.chat = {
  hits: (p, d) => (p.messages || [1, 2]).slice(0, 4).map((_, i, a) => 0.25 + i * seq(d, a.length, 0.25, 0.55)),
  draw(t, p, d) {
    const msgs = (p.messages || [{ from: "them", text: "Bro, form reject ho gaya" }, { from: "me", text: "Size kitna hai?" }]).slice(0, 4), gap = seq(d, msgs.length, 0.25, 0.55);
    at(540, 1110, pop(t, 0), 0, () => phone(500, 900, (sw, sh) => {
      rr(0, 0, sw, 130, 0); ctx.fillStyle = C.light; ctx.fill(); line(0, 130, sw, 130, 4);
      avatar(80, 80, 34, p.look || 2);
      txt(p.name || "Rahul", 135, 92, { size: 34, weight: 700 });
      let y = 190;
      msgs.forEach((m, i) => {
        const a = 0.25 + i * gap; if (t < a) return;
        const me = m.from === "me", lines = wrapLines(m.text, sw * 0.62, 32, 500).slice(0, 3);
        font(32, 500); const bw = Math.max(...lines.map(l => ctx.measureText(l).width)) + 50, bh = lines.length * 40 + 34;
        const x = me ? sw - 30 - bw : 30, s = pop(t, a, 0.25);
        at(x + bw / 2, y + bh / 2, s, 0, () => {
          card(-bw / 2, -bh / 2, bw, bh, { r: 24, fill: me ? C.coral : C.white, shadow: 5, lw: 4 });
          lines.forEach((l, k) => txt(l, -bw / 2 + 25, -bh / 2 + 44 + k * 40, { size: 32, weight: 500, color: me ? C.white : C.ink }));
        });
        y += bh + 26;
      });
    }));
  },
};
S.search = {
  hits: p => [1.0],
  draw(t, p) {
    const q = p.query || "how to resize photo to 50 kb";
    at(540, 760, pop(t, 0), 0, () => {
      card(-450, -70, 900, 140, { r: 70 });
      circle(-370, -6, 26, null, C.ink, 7); line(-352, 14, -330, 36, 8);
      const n = Math.floor(q.length * prog(t, 0.15, 0.75)), s = q.slice(0, n) + (n < q.length && Math.floor(t * 5) % 2 ? "|" : "");
      txt(s, -310, 12, { size: fitSize(q, 720, 44, 500), weight: 500 });
    });
    const res = (p.results || [p.result || "Top result"]).slice(0, 3);
    res.forEach((r, i) => at(540, 1010 + i * 210, pop(t, 1.0 + i * 0.15), 0, () => {
      card(-450, -85, 900, 170, { r: 22, fill: i === 0 ? C.white : C.cream, shadow: i === 0 ? 10 : 6 });
      mono(i === 0 ? "// top result" : "// result", -400, -30, { size: 22, color: i === 0 ? C.coral : C.gray, weight: 700 });
      txt(r, -400, 30, { size: fitSize(r, 800, 40, 700), weight: 700 });
    }));
  },
};
C.cream = "#FBF8F4";
S.chart = {
  hits: p => [1.2],
  draw(t, p) {
    const up = p.direction !== "down", u = eOut(prog(t, 0.2, 1.0));
    at(540, 1080, pop(t, 0), 0, () => {
      card(-430, -380, 860, 760, { r: 26 });
      mono("// " + (p.label || "trend"), -370, -310, { size: 26 });
      for (let k = 0; k < 4; k++) line(-370, -200 + k * 130, 370, -200 + k * 130, 3, C.light);
      const pts = up ? [[-370, 250], [-250, 200], [-130, 220], [-10, 120], [110, 140], [230, 10], [370, -200]] : [[-370, -200], [-250, -120], [-130, -150], [-10, 0], [110, -20], [230, 120], [370, 250]];
      ctx.beginPath(); let last = pts[0];
      ctx.moveTo(...pts[0]);
      const total = pts.length - 1, reach = u * total;
      for (let i = 1; i <= total; i++) { const f = clamp(reach - (i - 1)); if (f <= 0) break; const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; last = [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f]; ctx.lineTo(...last); }
      ctx.lineWidth = 12; ctx.strokeStyle = C.coral; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.stroke();
      circle(last[0], last[1], 18, C.white, C.ink, 6);
    });
    if (p.value) at(800, 640, pop(t, 1.2), 0.08, () => pill(0, 0, p.value, { fill: C.ink, size: 54 }));
  },
};
S.checklist = {
  hits: (p, d) => (p.items || [1, 2, 3]).slice(0, 4).map((_, i, a) => 0.35 + i * seq(d, a.length, 0.35, 0.45)),
  draw(t, p, d) {
    const items = (p.items || ["Photo under 50 KB", "Signature under 20 KB", "PDF under 200 KB"]).slice(0, 4), gap = seq(d, items.length, 0.35, 0.45);
    at(540, 1080, pop(t, 0), -0.02, () => {
      const h = 160 + items.length * 150;
      card(-420, -h / 2, 840, h, { r: 26 });
      mono("// " + (p.title || "checklist"), -360, -h / 2 + 70, { size: 26 });
      items.forEach((it, i) => {
        const y = -h / 2 + 170 + i * 150, a = 0.35 + i * gap, done = t > a;
        rr(-360, y - 40, 80, 80, 14); ctx.fillStyle = done ? C.coral : C.white; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke();
        if (done) { const k = eOut(prog(t, a, 0.2)); ctx.beginPath(); ctx.moveTo(-342, y); ctx.lineTo(-324, y + 20 * k); ctx.lineTo(-324 + 44 * k, y - 22 * k); ctx.lineWidth = 9; ctx.strokeStyle = C.white; ctx.lineCap = "round"; ctx.stroke(); }
        txt(it, -240, y + 14, { size: fitSize(it, 580, 46, 600), weight: 600, color: done ? C.ink : C.gray });
      });
    });
  },
};
S.versus = {
  hits: p => [0.9],
  draw(t, p) {
    const right = p.winner !== "left";
    [["left", 285, -0.05, 0], ["right", 795, 0.05, 0.3]].forEach(([k, x, rot, a]) => {
      const win = (k === "right") === right;
      at(x, 1080, pop(t, a), rot, () => {
        card(-220, -300, 440, 600, { r: 26, fill: win && t > 0.9 ? C.white : C.cream });
        mono("// " + (p[k + "_label"] || (k === "left" ? "the old way" : "the smart way")), 0, -220, { size: 24, align: "center" });
        const v = p[k] || (k === "left" ? "Cyber cafe" : "Your phone");
        para(v, 0, -80, 380, fitSize(v, 380, 64), { weight: 700, align: "center", max: 3 });
        if (p[k + "_sub"]) mono(p[k + "_sub"], 0, 200, { size: 26, align: "center", color: win ? C.coral : C.gray, weight: 700 });
      });
    });
    at(540, 1080, pop(t, 0.6), 0, () => { circle(0, 0, 66, C.ink, C.ink, 4); txt("VS", 0, 4, { size: 54, weight: 700, color: C.white, align: "center", base: "middle" }); });
    if (t > 0.9) at(right ? 795 : 285, 735, pop(t, 0.9), 0, () => {
      ctx.beginPath(); ctx.moveTo(-90, 40); ctx.lineTo(-100, -40); ctx.lineTo(-45, 0); ctx.lineTo(0, -60); ctx.lineTo(45, 0); ctx.lineTo(100, -40); ctx.lineTo(90, 40); ctx.closePath();
      ctx.fillStyle = C.gold; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = C.ink; ctx.stroke();
    });
  },
};
S.big_text = {
  hits: p => [0.35],
  draw(t, p) {
    const s = String(p.text || "3 SECONDS").toUpperCase();
    at(540, 1040, pop(t, 0.05, 0.4), -0.04, () => {
      const size = fitSize(s, 900, 220);
      txt(s, 0, 0, { size, weight: 700, color: C.coral, align: "center", base: "middle" });
      font(size, 700); const w = ctx.measureText(s).width, u = eOut(prog(t, 0.35, 0.35));
      ctx.beginPath(); for (let x = 0; x <= w * u; x += 20) ctx.lineTo(-w / 2 + x, size * 0.62 + Math.sin(x / 26) * 10); ctx.lineWidth = 10; ctx.strokeStyle = C.ink; ctx.lineCap = "round"; ctx.stroke();
    });
    if (p.sub) at(540, 1330, pop(t, 0.6), 0, () => mono(String(p.sub).toUpperCase(), 0, 0, { size: 36, color: C.ink, align: "center", weight: 700, ls: 4 }));
  },
};
S.person = {
  hits: p => [0.55],
  draw(t, p) {
    at(330, 1150, pop(t, 0), -0.03, () => {
      card(-200, -260, 400, 520, { r: 26 });
      avatar(0, -60, 130, p.look || 3);
      txt(p.name || "Priya", 0, 140, { size: fitSize(p.name || "Priya", 340, 52), weight: 700, align: "center" });
      mono("// " + (p.role || "student"), 0, 190, { size: 24, align: "center" });
    });
    if (p.quote) at(700, 760, pop(t, 0.55), 0.04, () => {
      const lines = wrapLines(p.quote, 420, 40, 600).slice(0, 4), h = lines.length * 50 + 70;
      card(-250, -h / 2, 500, h, { r: 30, fill: C.white });
      ctx.beginPath(); ctx.moveTo(-160, h / 2 - 3); ctx.lineTo(-210, h / 2 + 70); ctx.lineTo(-100, h / 2 - 3); ctx.closePath(); ctx.fillStyle = C.white; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke();
      rr(-163, h / 2 - 8, 60, 14, 0); ctx.fillStyle = C.white; ctx.fill();
      lines.forEach((l, i) => txt(l, -210, -h / 2 + 62 + i * 50, { size: 40, weight: 600 }));
    });
  },
};
S.timeline = {
  hits: (p, d) => (p.items || [1, 2, 3]).slice(0, 4).map((_, i, a) => 0.25 + i * seq(d, a.length, 0.25, 0.45)),
  draw(t, p, d) {
    const items = (p.items || [{ time: "1993", text: "PDF is born" }, { time: "2008", text: "Free for everyone" }, { time: "Today", text: "Every form wants one" }]).slice(0, 4);
    const top = 620, gap = Math.min(250, 900 / items.length), step = seq(d, items.length, 0.25, 0.45);
    line(230, top, 230, top + gap * (items.length - 1) * eOut(prog(t, 0.1, 0.4 + items.length * step)), 7);
    items.forEach((it, i) => {
      const a = 0.25 + i * step, y = top + i * gap, s = pop(t, a);
      at(230, y, s, 0, () => circle(0, 0, 26, i === items.length - 1 ? C.coral : C.white, C.ink, 6));
      at(300, y, s, 0, () => {
        txt(String(it.time || ""), 0, -8, { size: 56, weight: 700, color: C.coral, family: SERIF, style: "italic" });
        txt(String(it.text || ""), 0, 52, { size: fitSize(String(it.text || ""), 640, 44), weight: 600 });
      });
    });
  },
};
S.bulb = {
  hits: p => [0.5],
  draw(t, p) {
    const on = t > 0.5, u = eOut(prog(t, 0.5, 0.4));
    if (on) for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i - 4.5) * 0.32, r1 = 250, r2 = 250 + 90 * u; line(540 + Math.cos(a) * r1, 980 + Math.sin(a) * r1, 540 + Math.cos(a) * r2, 980 + Math.sin(a) * r2, 9, C.coral); }
    at(540, 1000, pop(t, 0), 0, () => {
      if (on) { const g = ctx.createRadialGradient(0, -20, 20, 0, -20, 300); g.addColorStop(0, `rgba(232,182,76,${0.5 * u})`); g.addColorStop(1, "rgba(232,182,76,0)"); ctx.fillStyle = g; ctx.fillRect(-320, -340, 640, 640); }
      ctx.beginPath(); ctx.arc(0, -40, 170, Math.PI * 0.78, Math.PI * 2.22); ctx.lineTo(70, 190); ctx.lineTo(-70, 190); ctx.closePath();
      ctx.fillStyle = on ? "#FFE7A6" : C.white; ctx.fill(); ctx.lineWidth = 7; ctx.strokeStyle = C.ink; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-40, 160); ctx.lineTo(-40, 40); ctx.quadraticCurveTo(0, -10, 40, 40); ctx.lineTo(40, 160); ctx.lineWidth = 6; ctx.strokeStyle = on ? C.coral : C.gray; ctx.stroke();
      for (let k = 0; k < 3; k++) { rr(-80, 195 + k * 36, 160, 30, 10); ctx.fillStyle = k % 2 ? C.gray : C.ink; ctx.fill(); }
    });
    if (p.text) at(540, 1480, pop(t, 0.8), -0.02, () => pill(0, 0, p.text, { fill: C.ink, size: 44 }));
  },
};
S.money = {
  hits: p => [0.8],
  draw(t, p) {
    const r = rng(5);
    for (let i = 0; i < 6; i++) at(380 + i * 18, 1240 - i * 46, pop(t, 0.05 * i, 0.25), 0, () => {
      ctx.beginPath(); ctx.ellipse(0, 0, 150, 46, 0, 0, Math.PI * 2); ctx.fillStyle = C.gold; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = C.ink; ctx.stroke();
      ctx.beginPath(); ctx.ellipse(0, -6, 110, 28, 0, 0, Math.PI * 2); ctx.lineWidth = 3; ctx.stroke();
    });
    at(720, 900, pop(t, 0.3), 0.1, () => {
      card(-200, -110, 400, 220, { r: 14, fill: "#CFE6C9" });
      circle(0, 0, 62, null, C.ink, 4);
      txt(p.symbol || "₹", 0, 6, { size: 70, weight: 700, align: "center", base: "middle" });
    });
    const amt = p.amount || "₹0";
    at(540, 1480, pop(t, 0.8), -0.03, () => pill(0, 0, amt, { fill: p.crossed ? C.ink : C.coral, size: 70 }));
    if (p.crossed && t > 0.95) { font(70, 700); const w = ctx.measureText(amt).width; line(540 - w / 2 - 20, 1480, 540 - w / 2 - 20 + (w + 40) * eOut(prog(t, 0.95, 0.2)), 1480, 10, C.coral); }
    if (p.text) mono(p.text, 540, 1590, { size: 28, align: "center" });
  },
};
S.notification = {
  hits: p => [0.45],
  draw(t, p) {
    at(540, 1110, pop(t, 0), 0, () => phone(480, 880, (sw, sh) => {
      ctx.fillStyle = "#2A2427"; ctx.fillRect(0, 0, sw, sh);
      txt(p.time || "9:41", sw / 2, 230, { size: 120, weight: 600, color: "#F3EEE7", align: "center" });
      mono(p.day || "Monday", sw / 2, 290, { size: 26, color: "#bdb3b6", align: "center" });
      const y = 380 + (1 - eOut(prog(t, 0.45, 0.3))) * -200;
      if (t > 0.45) {
        ctx.globalAlpha = eOut(prog(t, 0.45, 0.2));
        card(24, y, sw - 48, 200, { r: 30, fill: C.white, shadow: 0 });
        rr(50, y + 30, 64, 64, 16); ctx.fillStyle = C.coral; ctx.fill();
        mono((p.app || "MESSAGES").toUpperCase(), 130, y + 70, { size: 22, color: C.gray, weight: 700 });
        txt(p.title || "Form update", 50, y + 135, { size: fitSize(p.title || "Form update", sw - 120, 36), weight: 700 });
        txt(p.text || "Your application was rejected", 50, y + 178, { size: fitSize(p.text || "", sw - 120, 30, 500), weight: 500, color: C.gray });
        ctx.globalAlpha = 1;
      }
    }));
  },
};
S.warning = {
  hits: p => [0.3],
  draw(t, p) {
    const sh = t > 0.3 && t < 0.7 ? Math.sin(t * 60) * 0.04 : 0;
    at(540, 1000, pop(t, 0), sh, () => {
      ctx.beginPath(); ctx.moveTo(0, -260); ctx.lineTo(280, 220); ctx.lineTo(-280, 220); ctx.closePath();
      ctx.save(); ctx.translate(12, 12); ctx.fillStyle = DOTS; ctx.fill(); ctx.restore();
      ctx.beginPath(); ctx.moveTo(0, -260); ctx.lineTo(280, 220); ctx.lineTo(-280, 220); ctx.closePath();
      ctx.fillStyle = C.coral; ctx.fill(); ctx.lineWidth = 8; ctx.strokeStyle = C.ink; ctx.lineJoin = "round"; ctx.stroke();
      rr(-22, -120, 44, 200, 22); ctx.fillStyle = C.white; ctx.fill(); circle(0, 150, 26, C.white, null);
    });
    if (p.text) at(540, 1380, pop(t, 0.5), -0.03, () => pill(0, 0, p.text, { fill: C.ink, size: 46 }));
  },
};
S.fallback = S.stamp;

// ---------- frame ----------
function shotAt(t) { const s = REEL.shots; let i = 0; while (i + 1 < s.length && t >= s[i + 1].start) i++; return i; }
function wipe(t) {
  // coral wave that sweeps up the screen at the start of the last shot
  if (t > 0.55) return;
  const u = t < 0.28 ? eInOut(t / 0.28) : 1, v = t < 0.28 ? 0 : eInOut((t - 0.28) / 0.27);
  const top = H - u * (H + 120), bottom = H - v * (H + 160);
  ctx.beginPath(); ctx.moveTo(0, bottom);
  for (let x = 0; x <= W; x += 30) ctx.lineTo(x, top + Math.sin(x / 120 + t * 10) * 40);
  ctx.lineTo(W, bottom); ctx.closePath(); ctx.fillStyle = C.coral; ctx.fill();
}
window.frame = function (t) {
  const i = shotAt(t), sh = REEL.shots[i], lt = t - sh.start, sc = S[sh.scene.type] || S.fallback;
  const dark = !!sc.dark;
  background(t, dark);
  header(sh, t, dark);
  const hits = sc.hits ? sc.hits(sh.scene, sh.end - sh.start) : [];
  let dx = 0, dy = 0;
  for (const h of hits) if (lt > h && lt < h + 0.22) { const k = 1 - (lt - h) / 0.22; dx += Math.sin(lt * 90) * 10 * k; dy += Math.cos(lt * 75) * 8 * k; }
  ctx.save(); ctx.translate(dx, dy);
  try { sc.draw(lt, sh.scene, sh.end - sh.start); } catch (e) { console.log("scene error", sh.scene.type, e.message); }
  ctx.restore();
  headline(i, t, dark);
  mono("ilovedocuments.ai", W / 2, H - 70, { size: 26, color: dark ? "#6f6569" : "#b3aaa2", align: "center" });
  if (sc.wipe) wipe(lt);
  return cv.toDataURL("image/jpeg", 0.92);
};
window.load = async function (reel) {
  REEL = reel; LAYOUT = {};
  await Promise.all(["700 40px SG", "600 40px SG", "italic 400 40px IS", "400 20px SM", "700 20px SM", "700 40px Poppins"].map(f => document.fonts.load(f)));
  makeBackgrounds();
  return true;
};
window.ready = true;
