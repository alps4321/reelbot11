// Low-poly 3D story engine. Python sends a storyboard (list of shots) with
// window.load(shots), then asks for one frame at a time with window.frame(i, lt, t).
import * as THREE from '/studio/three.min.js';

const W = 1080, H = 1920;
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const SHIRTS = { orange: 0xf2622e, blue: 0x2f6fe4, green: 0x1fa56b, red: 0xd93a4a, purple: 0x7a4be0,
                 yellow: 0xf2b824, teal: 0x16a3a3, pink: 0xe56aa0, grey: 0x8a93a6 };
const SKINS = [0xf1c9a5, 0xc98f62, 0x8d5a3b, 0xe0ac7e];
const HAIR = [0x1b1b22, 0x3a2416, 0x101018, 0x5a3a1a];

const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.85, ...extra });
function mesh(geo, material, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(geo, material);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}
const box = (w, h, d, c, x, y, z, extra) => mesh(new THREE.BoxGeometry(w, h, d), mat(c, extra), x, y, z);

// ---------- 2D canvas textures (screens, signs, floating numbers) ----------
function rounded(g, x, y, w, h, r) {
  g.beginPath(); g.roundRect(x, y, w, h, r); g.fill();
}
function textTexture(draw, w = 512, h = 512) {
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d');
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.redraw = (lt) => { g.clearRect(0, 0, w, h); draw(g, w, h, lt); tex.needsUpdate = true; };
  tex.redraw(0);
  return tex;
}
const sizeKb = (s) => { const m = /([\d.]+)\s*(KB|MB)/i.exec(s || ''); return m ? parseFloat(m[1]) * (m[2].toUpperCase() === 'MB' ? 1024 : 1) : 0; };
const fmtSize = (kb) => kb >= 1000 ? (kb / 1024).toFixed(1) + ' MB' : Math.round(kb) + ' KB';
const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);

// The floating card: file row + error / success / shrinking size bar / plain text.
function drawPanel(p) {
  return (g, w, h, lt) => {
    g.fillStyle = '#ffffff'; rounded(g, 0, 0, w, h, 56);
    if (p.show === 'text') {
      g.fillStyle = '#141a28'; g.textAlign = 'center'; g.textBaseline = 'middle';
      const lines = String(p.text || '').split('\n').slice(0, 3);
      g.font = '700 ' + (lines.length > 1 ? 92 : 120) + 'px Poppins';
      lines.forEach((ln, i) => g.fillText(ln, w / 2, h / 2 + (i - (lines.length - 1) / 2) * 120, w - 80));
      return;
    }
    const ext = (String(p.file || 'file').split('.').pop() || 'file').toUpperCase().slice(0, 4);
    g.fillStyle = '#3468e8'; rounded(g, 50, 50, 130, 130, 28);
    g.fillStyle = '#fff'; g.font = '700 42px Poppins'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(ext, 115, 118);
    g.fillStyle = '#141a28'; g.font = '500 56px Poppins'; g.textAlign = 'left';
    g.fillText(p.file || 'file', 215, 118, 380);
    g.textAlign = 'right'; g.font = '700 62px Poppins';
    if (p.show === 'size_drop') {
      const a = sizeKb(p.from), b = sizeKb(p.to), k = ease((lt - 0.4) / 1.0), now = a + (b - a) * k;
      const col = `rgb(${Math.round(226 - 196 * k)},${Math.round(61 + 109 * k)},${Math.round(72 + 28 * k)})`;
      g.fillStyle = col; g.fillText(fmtSize(now), w - 50, 118);
      g.fillStyle = '#e4e7ee'; rounded(g, 50, 250, w - 100, 70, 35);
      g.fillStyle = col; rounded(g, 50, 250, (w - 100) * Math.max(0.07, now / a), 70, 35);
      g.font = '500 50px Poppins'; g.textAlign = 'left'; g.fillStyle = '#78808f'; g.fillText(p.from, 50, 400);
      if (k >= 1) { g.textAlign = 'right'; g.font = '700 56px Poppins'; g.fillStyle = '#1eaa64';
        g.fillText(Math.round(100 * (1 - b / a)) + '% smaller', w - 50, 400); }
      return;
    }
    const bad = p.show === 'error', col = bad ? '#e23d48' : '#1eaa64';
    g.fillStyle = col; g.fillText(p.size || '', w - 50, 118);
    if (lt >= 0.3) {
      rounded(g, 50, 240, w - 100, 190, 40);
      g.strokeStyle = '#fff'; g.lineWidth = 14; g.lineCap = 'round'; g.beginPath();
      if (bad) { g.moveTo(110, 305); g.lineTo(170, 365); g.moveTo(170, 305); g.lineTo(110, 365); }
      else { g.moveTo(105, 338); g.lineTo(132, 365); g.lineTo(178, 305); }
      g.stroke();
      g.fillStyle = '#fff'; g.textAlign = 'left'; g.font = '700 52px Poppins';
      g.fillText(p.message || (bad ? 'Upload failed' : 'Uploaded'), 215, 338, w - 300);
    }
  };
}

function label3d(text, color = '#ffffff', size = 1) {
  const tex = textTexture((g, w, h) => {
    g.font = '700 150px Poppins'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = 22; g.strokeStyle = 'rgba(0,0,0,0.55)'; g.strokeText(text, w / 2, h / 2, w - 40);
    g.fillStyle = color; g.fillText(text, w / 2, h / 2, w - 40);
  }, 1024, 256);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  s.scale.set(2.4 * size, 0.6 * size, 1);
  return s;
}

// ---------- characters ----------
// Chibi cartoon cast: big heads, toon shading, black outlines, faces that change with the pose.
const TOON = (() => { const d = new Uint8Array([90, 170, 255]); const t = new THREE.DataTexture(d, 3, 1, THREE.RedFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter; t.needsUpdate = true; return t; })();
const toon = (color, extra = {}) => new THREE.MeshToonMaterial({ color, gradientMap: TOON, ...extra });
const INK = new THREE.MeshBasicMaterial({ color: 0x1b1222, side: THREE.BackSide });
function inked(geo, material, x = 0, y = 0, z = 0, w = 0.035) {   // mesh plus a black outline shell
  const g = new THREE.Group(); g.position.set(x, y, z);
  const m = new THREE.Mesh(geo, material); m.castShadow = true; m.receiveShadow = true; g.add(m);
  if (!w) return g;                 // open shapes (hair caps, arcs) get no shell: its inside would show
  geo.computeBoundingSphere();
  const r = geo.boundingSphere.radius || 1, o = new THREE.Mesh(geo, INK); o.scale.setScalar(1 + w / r); g.add(o);
  return g;
}
const plain = (geo, color, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color })); m.position.set(x, y, z); return m; };

function makeFace(head, R, look) {
  const f = {};
  f.eyes = [-1, 1].map((s) => {
    const e = new THREE.Group(); e.position.set(0.15 * s, 0.05, R * 0.9);
    const white = plain(new THREE.SphereGeometry(1, 20, 14), 0xffffff); white.scale.set(0.1, 0.125, 0.05); e.add(white);
    const pupil = plain(new THREE.SphereGeometry(1, 16, 12), 0x16121c, 0.005, -0.01, 0.04); pupil.scale.set(0.058, 0.07, 0.03); e.add(pupil);
    const shine = plain(new THREE.SphereGeometry(1, 10, 8), 0xffffff, 0.025, 0.03, 0.065); shine.scale.setScalar(0.02); e.add(shine);
    e.userData.pupil = pupil; head.add(e); return e;
  });
  f.brows = [-1, 1].map((s) => { const b = plain(new THREE.BoxGeometry(0.13, 0.03, 0.02), 0x23181a, 0.15 * s, 0.22, R * 0.93); head.add(b); return b; });
  const lip = 0x7a2430;
  f.smile = plain(new THREE.TorusGeometry(0.075, 0.016, 8, 20, Math.PI), lip, 0, -0.12, R * 0.95); f.smile.rotation.z = Math.PI;
  f.frown = plain(new THREE.TorusGeometry(0.07, 0.016, 8, 20, Math.PI), lip, 0, -0.17, R * 0.95);
  f.open = new THREE.Group(); f.open.position.set(0, -0.14, R * 0.93);
  const hole = plain(new THREE.SphereGeometry(1, 18, 12), 0x5a1020); hole.scale.set(0.085, 0.07, 0.03); f.open.add(hole);
  const tongue = plain(new THREE.SphereGeometry(1, 12, 8), 0xff6f7d, 0, -0.03, 0.012); tongue.scale.set(0.05, 0.025, 0.02); f.open.add(tongue);
  [f.smile, f.frown, f.open].forEach((m) => head.add(m));
  [-1, 1].forEach((s) => { const c = new THREE.Mesh(new THREE.CircleGeometry(0.06, 16), new THREE.MeshBasicMaterial({ color: 0xff7a8a, transparent: true, opacity: 0.45 }));
    c.position.set(0.25 * s, -0.06, R * 0.86); c.rotation.y = 0.35 * s; head.add(c); });
  return f;
}

function hairFor(head, R, who, color) {
  const hair = toon(color);
  if (who === 'uncle') {          // grey sides, shiny top, big moustache, round specs
    const ring = inked(new THREE.TorusGeometry(R * 0.82, 0.11, 10, 24, Math.PI * 1.3), toon(0x9aa0a8), 0, 0.02, -0.04, 0);
    ring.rotation.set(Math.PI / 2, 0, Math.PI * 0.85); head.add(ring);
    const mo = inked(new THREE.CapsuleGeometry(0.05, 0.2, 6, 12), toon(0x5d5a5a), 0, -0.07, R * 0.95, 0.015); mo.rotation.z = Math.PI / 2; head.add(mo);
    [-1, 1].forEach((s) => { const g = plain(new THREE.TorusGeometry(0.09, 0.014, 8, 24), 0x22222a, 0.15 * s, 0.05, R * 0.98); head.add(g); });
    head.add(plain(new THREE.BoxGeometry(0.1, 0.014, 0.014), 0x22222a, 0, 0.07, R * 0.99));
    return;
  }
  const cap = inked(new THREE.SphereGeometry(R * 1.04, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.5), hair, 0, 0.04, -0.03, 0);
  cap.rotation.x = -0.25; head.add(cap);
  if (who === 'pappu') {          // a cheeky spiky tuft
    [[-0.1, 0.3], [0.05, 0.45], [0.18, 0.28]].forEach(([x, rz], i) => {
      const t = inked(new THREE.ConeGeometry(0.09, 0.28, 8), hair, x, R * 0.98, 0.05 + i * 0.03, 0.015); t.rotation.z = -rz + 0.3; head.add(t);
    });
  } else if (who === 'girl') {    // two buns and a fringe
    [-1, 1].forEach((s) => head.add(inked(new THREE.SphereGeometry(0.17, 16, 12), hair, 0.3 * s, R * 0.82, -0.05, 0.02)));
    const fringe = inked(new THREE.CapsuleGeometry(0.07, 0.34, 6, 12), hair, 0.02, R * 0.62, R * 0.62, 0.015); fringe.rotation.z = Math.PI / 2 + 0.15; head.add(fringe);
  }
}

function makeActor(spec, index) {
  if (spec.mascot) return makeMascot(spec);
  const g = new THREE.Group();
  const who = spec.tie ? 'uncle' : spec.color === 'purple' ? 'girl' : spec.color === 'orange' ? 'pappu' : 'other';
  const shirt = toon(SHIRTS[spec.color] || Object.values(SHIRTS)[index % 9]);
  const skin = toon(SKINS[(spec.skin ?? (who === 'uncle' ? 1 : index)) % SKINS.length]);
  const pants = toon(who === 'uncle' ? 0x3b3f4a : 0x2b3a67), shoe = toon(who === 'girl' ? 0xff6fa5 : 0xf2f2f2);
  const body = new THREE.Group(); g.add(body);
  const legs = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.15 * s, 0.7, 0);
    p.add(inked(new THREE.CapsuleGeometry(0.1, 0.42, 6, 12), pants, 0, -0.33, 0, 0.02));
    p.add(inked(new THREE.SphereGeometry(0.14, 16, 10), shoe, 0, -0.66, 0.06, 0.02));
    p.children[1].scale.set(1, 0.6, 1.4);
    body.add(p); return p;
  });
  const torso = new THREE.Group(); torso.position.y = 0.7; body.add(torso);
  const belly = inked(new THREE.CapsuleGeometry(0.3, 0.3, 8, 16), shirt, 0, 0.32, 0, 0.025);
  belly.scale.set(who === 'uncle' ? 1.15 : 1, 1, who === 'uncle' ? 1.1 : 0.9); torso.add(belly);
  const arms = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.37 * s, 0.58, 0);
    p.add(inked(new THREE.CapsuleGeometry(0.08, 0.36, 6, 10), shirt, 0, -0.25, 0, 0.02));
    p.add(inked(new THREE.SphereGeometry(0.1, 14, 10), skin, 0, -0.55, 0, 0.015));
    torso.add(p); return p;
  });
  const R = 0.42;
  const head = new THREE.Group(); head.position.y = 1.1; torso.add(head);
  head.add(inked(new THREE.SphereGeometry(R, 32, 24), skin, 0, 0, 0, 0.03));
  [-1, 1].forEach((s) => head.add(inked(new THREE.SphereGeometry(0.08, 12, 8), skin, (R + 0.01) * s, -0.02, 0, 0.015)));   // ears
  hairFor(head, R, who, HAIR[index % HAIR.length]);
  const face = makeFace(head, R);
  if (spec.tie) { torso.add(inked(new THREE.ConeGeometry(0.08, 0.42, 4), toon(0xc0392b), 0, 0.4, 0.28, 0.012)); torso.children.at(-1).rotation.x = Math.PI; }
  let phone = null;
  if (spec.pose === 'phone') {
    phone = box(0.16, 0.3, 0.03, 0x111111, 0, -0.62, 0.08, { emissive: 0x9fd0ff, emissiveIntensity: 0.9 });
    arms[1].add(phone);
  }
  if (spec.float) { const f = label3d(spec.float.text, spec.float.color || '#ffffff', 0.8); f.position.y = 2.75; g.add(f); g.userData.float = f; }
  const turn = { left: -0.9, right: 0.9, camera: 0, away: Math.PI }[spec.look || 'camera'] ?? 0;
  g.position.set(spec.x ?? 0, 0, spec.z ?? 0);
  g.rotation.y = turn;
  if (who === 'uncle') g.scale.setScalar(1.08);
  g.userData = { ...g.userData, spec, body, torso, legs, arms, head, face, x0: spec.x ?? 0 };
  return g;
}

// Docu: the ilovedocuments.ai mascot, a cheerful PDF page with a red heart. It pops in to save the day.
function heartShape(s) {
  const h = new THREE.Shape(); h.moveTo(0, -0.9 * s);
  h.bezierCurveTo(-1.2 * s, -0.1 * s, -0.9 * s, 0.85 * s, 0, 0.35 * s);
  h.bezierCurveTo(0.9 * s, 0.85 * s, 1.2 * s, -0.1 * s, 0, -0.9 * s); return h;
}
function makeMascot(spec) {
  const g = new THREE.Group();
  const body = new THREE.Group(); g.add(body);
  const w = 1.0, h = 1.3, r = 0.14, ear = 0.3;
  const page = new THREE.Shape();
  page.moveTo(-w / 2 + r, -h / 2); page.lineTo(w / 2 - r, -h / 2); page.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  page.lineTo(w / 2, h / 2 - ear); page.lineTo(w / 2 - ear, h / 2); page.lineTo(-w / 2 + r, h / 2);
  page.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r); page.lineTo(-w / 2, -h / 2 + r); page.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  const geo = new THREE.ExtrudeGeometry(page, { depth: 0.14, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.04, bevelSegments: 3 });
  geo.translate(0, 0, -0.07);
  const sheet = inked(geo, toon(0xffffff), 0, 1.25, 0, 0.04); body.add(sheet);
  const fold = new THREE.Shape(); fold.moveTo(w / 2 - ear, h / 2); fold.lineTo(w / 2 - ear, h / 2 - ear); fold.lineTo(w / 2, h / 2 - ear);
  const foldM = new THREE.Mesh(new THREE.ShapeGeometry(fold), new THREE.MeshBasicMaterial({ color: 0xd6dbe6, side: THREE.DoubleSide }));
  foldM.position.set(0, 1.25, 0.13); body.add(foldM);
  const heart = new THREE.Mesh(new THREE.ExtrudeGeometry(heartShape(0.2), { depth: 0.06, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.02, bevelSegments: 2 }),
                               toon(0xe8344a, { emissive: 0x5a0010, emissiveIntensity: 0.25 }));
  heart.position.set(0, 0.8, 0.12); heart.scale.setScalar(0.8); body.add(heart);
  const brand = textTexture((g2, w2, h2) => {        // the site's name printed on Docu's page
    g2.textAlign = 'center'; g2.textBaseline = 'middle'; g2.font = '700 74px Poppins';
    g2.fillStyle = '#e8344a'; g2.fillText('ilove', w2 / 2, h2 * 0.3);
    g2.fillStyle = '#1b2a4a'; g2.font = '700 64px Poppins'; g2.fillText('documents.ai', w2 / 2, h2 * 0.74, w2 - 20);
  }, 512, 256);
  const label = new THREE.Mesh(new THREE.PlaneGeometry(0.78, 0.39), new THREE.MeshBasicMaterial({ map: brand, transparent: true }));
  label.position.set(-0.02, 1.13, 0.125); body.add(label);
  const head = new THREE.Group(); head.position.set(0, 1.5, -0.33); body.add(head);
  const face = makeFace(head, 0.5);
  const arms = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.55 * s, 1.15, 0);
    p.add(inked(new THREE.CapsuleGeometry(0.06, 0.3, 6, 10), toon(0xffffff), 0, -0.2, 0, 0.02));
    p.add(inked(new THREE.SphereGeometry(0.09, 12, 10), toon(0xffffff), 0, -0.44, 0, 0.02));
    body.add(p); return p;
  });
  const legs = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.2 * s, 0.6, 0);
    p.add(inked(new THREE.CapsuleGeometry(0.06, 0.22, 6, 10), toon(0xffffff), 0, -0.18, 0, 0.02));
    const sh = inked(new THREE.SphereGeometry(0.12, 14, 10), toon(0xe8344a), 0, -0.4, 0.05, 0.02); sh.scale.set(1, 0.6, 1.4); p.add(sh);
    body.add(p); return p;
  });
  const sparks = [];
  for (let i = 0; i < 6; i++) {
    const st = plain(new THREE.OctahedronGeometry(0.06, 0), 0xffd23a); body.add(st); sparks.push(st);
  }
  g.position.set(spec.x ?? 1.2, 0, spec.z ?? 0.5);
  g.rotation.y = { left: -0.5, right: 0.5, camera: 0 }[spec.look || 'left'] ?? -0.5;
  g.userData = { spec: { ...spec, pose: spec.pose || 'wave' }, body, torso: body, legs, arms, head, face, sparks, mascot: true, x0: spec.x ?? 1.2 };
  return g;
}

const MOOD = { panic: 'scared', yell: 'angry', sad: 'sad', cheer: 'happy', talk: 'talk', wave: 'happy', point: 'smile',
               stand: 'smile', walk: 'smile', sit: 'smile', type: 'smile', phone: 'smile' };
function setFace(f, mood, lt) {
  if (!f) return;
  const blink = (lt % 2.7) > 2.58 ? 0.15 : 1;
  f.eyes.forEach((e) => { e.scale.y = blink * (mood === 'scared' ? 1.2 : mood === 'angry' ? 0.8 : 1); const k = mood === 'scared' ? 0.75 : 1; e.userData.pupil.scale.set(0.058 * k, 0.07 * k, 0.03); });
  const brow = { angry: [-0.45, 0.02], scared: [0.4, 0.05], sad: [0.35, 0], happy: [-0.12, 0.05], talk: [-0.08, 0.03], smile: [0, 0] }[mood] || [0, 0];
  f.brows.forEach((b, i) => { b.rotation.z = (i ? -1 : 1) * brow[0]; b.position.y = 0.22 + brow[1]; });
  const talking = mood === 'talk' && Math.sin(lt * 14) > 0;
  const open = mood === 'scared' || mood === 'angry' || mood === 'happy' || talking;
  f.open.visible = open; f.smile.visible = !open && mood !== 'sad'; f.frown.visible = !open && mood === 'sad';
  f.open.scale.setScalar(mood === 'angry' ? 1.35 : mood === 'scared' ? 1.15 + Math.sin(lt * 20) * 0.08 : 1);
}

function poseMascot(a, lt) {
  const { body, arms, legs, sparks, face } = a.userData;
  const pop = lt < 0.45 ? Math.min(1, lt / 0.3) * (1 + 0.25 * Math.sin(Math.min(1, lt / 0.45) * Math.PI)) : 1;
  a.scale.setScalar(Math.max(0.01, pop));
  body.position.y = 0.12 + Math.sin(lt * 3.2) * 0.08;
  body.rotation.z = Math.sin(lt * 2.4) * 0.06;
  arms[0].rotation.z = -0.4 + Math.sin(lt * 3) * 0.1;
  arms[1].rotation.z = 2.3 + Math.sin(lt * 9) * 0.4;
  legs.forEach((l, i) => { l.rotation.x = Math.sin(lt * 6 + i * Math.PI) * 0.25; });
  sparks.forEach((s, i) => { const ang = lt * 1.6 + i * Math.PI / 3; s.position.set(Math.cos(ang) * 0.85, 1.3 + Math.sin(ang * 1.3) * 0.6, Math.sin(ang) * 0.3);
    s.rotation.set(lt * 3, lt * 2, 0); s.scale.setScalar(0.6 + 0.4 * Math.abs(Math.sin(lt * 4 + i))); });
  setFace(face, 'talk', lt);
}

function poseActor(a, lt) {
  if (a.userData.mascot) return poseMascot(a, lt);
  const { spec, body, torso, legs, arms, head, x0, face } = a.userData;
  const breathe = Math.sin(lt * 2.2) * 0.012;
  body.position.y = breathe; torso.rotation.set(0, 0, 0); head.rotation.set(0, Math.sin(lt * 0.9) * 0.08, Math.sin(lt * 1.3) * 0.04);
  legs.forEach((l) => l.rotation.set(0, 0, 0));
  arms.forEach((p, i) => p.rotation.set(0, 0, (i ? 1 : -1) * 0.12));
  setFace(face, MOOD[spec.pose] || 'smile', lt);
  switch (spec.pose) {
    case 'walk': {
      const s = Math.sin(lt * 7), dir = spec.look === 'left' ? -1 : 1;
      legs[0].rotation.x = s * 0.65; legs[1].rotation.x = -s * 0.65;
      arms[0].rotation.x = -s * 0.5; arms[1].rotation.x = s * 0.5;
      body.position.y = Math.abs(Math.cos(lt * 7)) * 0.05;
      a.position.x = x0 + dir * lt * 0.55; break;
    }
    case 'sit': case 'type':
      body.position.y = -0.32 + breathe; legs.forEach((l) => { l.rotation.x = -1.5; });
      if (spec.pose === 'type') arms.forEach((p, i) => { p.rotation.x = -1.15 + Math.sin(lt * 14 + i * 2) * 0.06; });
      else arms.forEach((p) => { p.rotation.x = -0.5; });
      break;
    case 'sad':
      torso.rotation.x = 0.18; head.rotation.x = 0.4; head.rotation.y = 0;
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * 0.04; }); break;
    case 'cheer':
      body.position.y = Math.abs(Math.sin(lt * 7)) * 0.25;
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * (2.6 + Math.sin(lt * 9) * 0.15); });
      head.rotation.x = -0.15; break;
    case 'phone':
      arms[1].rotation.x = -1.15; arms[1].rotation.z = -0.25; head.rotation.x = 0.28; head.rotation.y = 0.1; break;
    case 'point':
      arms[1].rotation.x = -1.45 + Math.sin(lt * 5) * 0.05; arms[1].rotation.z = 0.5; break;
    case 'panic':
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * 2.5; p.rotation.x = Math.sin(lt * 18 + i) * 0.3; });
      head.rotation.y = Math.sin(lt * 10) * 0.25; head.rotation.z = Math.sin(lt * 13) * 0.1;
      body.position.y = Math.abs(Math.sin(lt * 10)) * 0.08; break;
    case 'yell':
      torso.rotation.x = 0.22; head.rotation.x = -0.2 + Math.sin(lt * 22) * 0.06;
      arms.forEach((p, i) => { p.rotation.x = -1.3 + Math.sin(lt * 20 + i * 2) * 0.35; p.rotation.z = (i ? 1 : -1) * 0.5; });
      body.position.y = Math.abs(Math.sin(lt * 14)) * 0.05; a.position.x = x0 + Math.sin(lt * 30) * 0.02; break;
    case 'talk':
      arms[1].rotation.x = -0.95 + Math.sin(lt * 9) * 0.28; arms[1].rotation.z = 0.25;
      arms[0].rotation.x = -0.35 + Math.sin(lt * 7 + 1) * 0.15;
      head.rotation.x = Math.sin(lt * 8) * 0.07; body.position.y = breathe + Math.abs(Math.sin(lt * 8)) * 0.015; break;
    case 'wave':
      arms[1].rotation.z = 2.5 + Math.sin(lt * 8) * 0.35; break;
  }
  if (a.userData.float) a.userData.float.position.y = 2.75 + Math.sin(lt * 2) * 0.05;
}

// ---------- sets ----------
const SETS = {
  park:    { sky: ['#4f9df0', '#bfe3ff'], ground: 0x58c34a, sun: 0xfff2d6, amb: 0.9 },
  sunset:  { sky: ['#5b2a86', '#ff9a5a'], ground: 0x7b4a8c, sun: 0xffb070, amb: 0.7 },
  night:   { sky: ['#0a0d2a', '#2a1a55'], ground: 0x1b1d3a, sun: 0x8fa8ff, amb: 0.55 },
  bedroom: { sky: ['#2a1746', '#4a2670'], ground: 0x6a4a2e, sun: 0xffd9a0, amb: 0.65 },
  office:  { sky: ['#f0e3cf', '#f7efe2'], ground: 0x4a5f86, sun: 0xfff4e0, amb: 0.9 },
  exam:    { sky: ['#f3d7a6', '#fbeed6'], ground: 0xc9a777, sun: 0xfff1d0, amb: 0.9 },
};

function skyTexture(top, bottom) {
  const t = textTexture((g, w, h) => {
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, top); gr.addColorStop(1, bottom);
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
  }, 16, 512);
  return t;
}

function tree(x, z, s = 1) {
  const g = new THREE.Group();
  g.add(mesh(new THREE.CylinderGeometry(0.12 * s, 0.16 * s, 1.1 * s, 6), mat(0x6b4226), 0, 0.55 * s, 0));
  g.add(mesh(new THREE.IcosahedronGeometry(0.85 * s, 0), mat(0x2f9e44), 0, 1.7 * s, 0));
  g.add(mesh(new THREE.IcosahedronGeometry(0.6 * s, 0), mat(0x37b24d), 0.35 * s, 2.3 * s, 0.1));
  g.position.set(x, 0, z); return g;
}

function buildSet(scene, name) {
  const S = SETS[name] || SETS.park;
  scene.background = skyTexture(S.sky[0], S.sky[1]);
  scene.fog = new THREE.Fog(S.sky[1], 14, 34);
  scene.add(new THREE.HemisphereLight(0xffffff, S.ground, S.amb));
  const sun = new THREE.DirectionalLight(S.sun, 2.2);
  sun.position.set(4, 8, 6); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -7, right: 7, top: 9, bottom: -3, near: 1, far: 30 });
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x9fd8ff, 1.4); rim.position.set(-5, 6, -6); scene.add(rim);
  const ground = mesh(new THREE.PlaneGeometry(80, 80), mat(S.ground)); ground.rotation.x = -Math.PI / 2; ground.castShadow = false;
  scene.add(ground);
  if (name === 'park' || name === 'sunset') {
    [[-2.6, -2.5, 1.2], [2.7, -3, 1.4], [-4.5, -6, 1.6], [4.2, -7, 1.3], [0.4, -9, 1.7], [-1.6, -6.5, 1.1]].forEach(([x, z, s]) => scene.add(tree(x, z, s)));
    if (name === 'sunset') scene.add(mesh(new THREE.SphereGeometry(1.6, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffe2a0 }), 1.5, 4.5, -22));
  } else if (name === 'night') {
    const pts = []; for (let i = 0; i < 260; i++) pts.push((Math.random() - 0.5) * 50, 4 + Math.random() * 22, -22 - Math.random() * 6);
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.12 })));
    for (let i = 0; i < 9; i++) {
      const h = 3 + ((i * 37) % 7), x = -8 + i * 2, z = -9 - (i % 3);
      scene.add(box(1.6, h, 1.5, 0x141838, x, h / 2, z));
      for (let r = 0; r < h - 1; r++) for (let c = -1; c <= 1; c += 2) if ((i + r + c) % 3)
        scene.add(box(0.3, 0.35, 0.05, 0xffd772, x + c * 0.35, 0.9 + r, z + 0.78, { emissive: 0xffc84a, emissiveIntensity: 1 }));
    }
  } else {  // rooms: back wall, a window, simple furniture
    const wall = name === 'bedroom' ? 0x3a2260 : name === 'office' ? 0xf0e3cf : 0xf2deb8;
    scene.add(box(14, 8, 0.3, wall, 0, 4, -3.2));
    scene.add(box(1.7, 1.9, 0.1, name === 'bedroom' ? 0x16204a : 0xbfe3ff, -1.9, 3.3, -3.0,
                  { emissive: name === 'bedroom' ? 0x2b3f9a : 0xdff1ff, emissiveIntensity: 0.6 }));
    if (name === 'bedroom') {
      scene.add(box(1.9, 2.1, 0.06, 0x23124a, -1.9, 3.3, -3.02));                       // window frame
      scene.add(mesh(new THREE.SphereGeometry(0.28, 12, 10), new THREE.MeshBasicMaterial({ color: 0xfff3c4 }), -1.6, 3.7, -2.9));  // moon
      scene.add(box(2.4, 0.45, 1.3, 0x3d6ee0, 2.2, 0.23, -2.3)); scene.add(box(2.4, 1.0, 0.15, 0x6b4a2a, 2.2, 0.5, -3.0));
      scene.add(box(0.7, 0.18, 0.5, 0xffffff, 2.2, 0.55, -2.7));
      scene.add(box(1.1, 1.4, 0.05, 0xf2b824, 1.9, 3.4, -3.0));                          // poster
      const rug = mesh(new THREE.CircleGeometry(1.7, 20), mat(0x8a3f6b), 0, 0.01, 0.3); rug.rotation.x = -Math.PI / 2; rug.castShadow = false; scene.add(rug);
      const lamp = new THREE.PointLight(0xffb060, 14, 9); lamp.position.set(-2.2, 2.2, 0.5); scene.add(lamp);
    }
    if (name === 'exam') for (let i = -1; i <= 1; i++) scene.add(box(1.1, 0.75, 0.6, 0x9a6b3c, i * 2.2, 0.38, -1.9));
    if (name === 'office') {
      const carpet = mesh(new THREE.PlaneGeometry(14, 9), mat(0x34507a), 0, 0.01, 0.5); carpet.rotation.x = -Math.PI / 2; carpet.castShadow = false; scene.add(carpet);
      scene.add(box(14, 0.5, 0.32, 0x2a3b5c, 0, 0.25, -3.15));                              // skirting
      scene.add(box(1.6, 1.0, 0.08, 0xffffff, 2.0, 3.2, -3.0)); scene.add(box(1.7, 1.1, 0.05, 0x39424f, 2.0, 3.2, -3.03));  // whiteboard
      [-2.6, 2.7].forEach((x) => {
        scene.add(box(1.6, 0.08, 0.8, 0xc9a777, x, 0.9, -2.2)); scene.add(box(0.1, 0.9, 0.7, 0x8a6b42, x - 0.7, 0.45, -2.2)); scene.add(box(0.1, 0.9, 0.7, 0x8a6b42, x + 0.7, 0.45, -2.2));
        scene.add(box(0.7, 0.45, 0.05, 0x10131c, x, 1.3, -2.3, { emissive: 0x7fb4ff, emissiveIntensity: 0.8 })); scene.add(box(0.08, 0.2, 0.08, 0x333a48, x, 1.0, -2.3));
      });
      scene.add(mesh(new THREE.CylinderGeometry(0.22, 0.17, 0.4, 8), mat(0xc96f3b), -0.2, 0.2, -2.6)); scene.add(mesh(new THREE.IcosahedronGeometry(0.5, 0), mat(0x2f9e44), -0.2, 0.85, -2.6));
    }
  }
}

function addProp(scene, p, list) {
  const x = p.x ?? 0;
  if (p.type === 'bench') {
    scene.add(box(1.9, 0.1, 0.55, 0x9a6b3c, x, 0.5, -0.15)); scene.add(box(1.9, 0.55, 0.08, 0x9a6b3c, x, 0.95, -0.42));
    [-0.8, 0.8].forEach((d) => scene.add(box(0.1, 0.5, 0.5, 0x4a3524, x + d, 0.25, -0.15)));
  } else if (p.type === 'desk') {
    scene.add(box(1.7, 0.08, 0.8, 0x9a6b3c, x, 0.82, 0.55));
    [-0.75, 0.75].forEach((d) => scene.add(box(0.08, 0.82, 0.7, 0x6b4a2a, x + d, 0.41, 0.55)));
    scene.add(box(0.6, 0.03, 0.4, 0x2a2f3d, x, 0.88, 0.6));
    scene.add(box(0.6, 0.4, 0.03, 0x10131c, x, 1.08, 0.82, { emissive: p.state === 'error' ? 0xff4a57 : 0x7fb4ff, emissiveIntensity: 0.9 }));
    scene.add(box(0.5, 0.45, 0.5, 0x3b4252, x, 0.42, -0.1));  // stool under the sitter
  } else if (p.type === 'clock') {
    const tex = textTexture((g, w, h) => {
      g.fillStyle = '#10131c'; rounded(g, 0, 0, w, h, 50);
      g.fillStyle = p.color || '#ff5a66'; g.font = '700 150px Poppins'; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(p.text || '11:58 PM', w / 2, h / 2, w - 50);
    }, 768, 256);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2.1, 0.7), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
    m.position.set(x, p.y ?? 3.2, -1.2); scene.add(m);
    list.push((lt) => { m.scale.setScalar(1 + Math.sin(lt * 6) * 0.03); });
  } else if (p.type === 'panel') {
    const tex = textTexture(drawPanel(p), 900, 500);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 1.5), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 1.5), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25 }));
    const g = new THREE.Group(); shadow.position.set(0.07, -0.09, -0.02); g.add(shadow, m);
    g.position.set(x, p.y ?? 3.05, 0.2); scene.add(g);
    list.push((lt) => {
      tex.redraw(lt);
      const k = ease(lt / 0.3);
      g.scale.setScalar(0.6 + 0.4 * k + (k >= 1 ? 0 : 0.08 * Math.sin(k * Math.PI)));
      g.position.y = (p.y ?? 3.05) + Math.sin(lt * 1.8) * 0.05;
      g.rotation.z = p.show === 'error' && lt > 0.3 && lt < 0.8 ? Math.sin(lt * 50) * 0.04 : 0;
    });
  } else if (p.type === 'paper') {
    const m = box(0.5, 0.66, 0.02, 0xffffff, x, p.y ?? 2.9, 0.5);
    scene.add(m); list.push((lt) => { m.rotation.y = lt * 1.6; m.position.y = (p.y ?? 2.9) + Math.sin(lt * 2.5) * 0.1; });
  }
}

// ---------- camera ----------
function cameraFor(shot, focus) {
  const cam = new THREE.PerspectiveCamera(50, W / H, 0.1, 80);
  const look = new THREE.Vector3(focus, 1.9, 0);
  const hasPanel = (shot.props || []).some((p) => p.type === 'panel');
  const moves = {
    wide:    (k) => [focus, 2.0, 7.0 - 0.5 * k],
    close:   (k) => [focus + 0.3, 2.1, 4.9 - 0.3 * k],
    push_in: (k) => [focus, 2.0, 7.6 - (hasPanel ? 1.2 : 2.8) * ease(k)],
    orbit:   (k) => [focus + Math.sin(-0.35 + 0.7 * k) * 6.8, 2.2, Math.cos(-0.35 + 0.7 * k) * 6.8],
    low:     (k) => [focus + 0.5, 0.7, 6.4 - 0.5 * k],
    high:    (k) => [focus, 5.0 - 0.5 * k, 7.8],
  };
  let name = shot.camera;
  if (hasPanel && !['wide', 'push_in', 'orbit'].includes(name)) name = 'push_in';
  const fn = moves[name] || moves.wide;
  return { cam, update: (k, lt) => { const [x, y, z] = fn(k); const j = shot.shake ? 0.07 * Math.exp(-lt * 1.2) : 0;
    cam.position.set(x + Math.sin(lt * 61) * j, y + Math.cos(lt * 53) * j, z); cam.lookAt(look); } };
}

// ---------- public API ----------
let shots = [];
window.load = (storyboard) => {
  shots = storyboard.map((shot) => {
    const scene = new THREE.Scene(), updaters = [];
    buildSet(scene, shot.set);
    const panel = (shot.props || []).some((p) => p.type === 'panel');
    const actors = (shot.actors || []).map((spec, i) => {
      const a = makeActor(panel && spec.float ? { ...spec, float: null } : spec, i); scene.add(a);   // the panel already says it
      if (spec.pose === 'sit') addProp(a, { type: 'bench', x: 0 }, updaters);
      if (spec.pose === 'type') { addProp(a, { type: 'desk', x: 0, state: spec.screen }, updaters); if (!spec.look) a.rotation.y = 0.75; }
      return a;
    });
    (shot.props || []).forEach((p) => addProp(scene, p, updaters));
    const xs = actors.filter((a) => a.userData.spec.pose !== 'walk').map((a) => a.position.x);
    const focus = xs.length ? (Math.min(...xs) + Math.max(...xs)) / 2 : 0;     // frame everyone, Docu included
    return { scene, actors, updaters, camera: cameraFor(shot, focus) };
  });
  return shots.length;
};

window.frame = (i, lt, k) => {
  const s = shots[i];
  s.actors.forEach((a) => poseActor(a, lt));
  s.updaters.forEach((u) => u(lt));
  s.camera.update(k, lt);
  renderer.render(s.scene, s.camera.cam);
  return canvas.toDataURL('image/jpeg', 0.93);
};

document.fonts.load('700 40px Poppins').then(() => document.fonts.load('500 40px Poppins')).then(() => { window.ready = true; });
