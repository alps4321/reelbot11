// Low-poly 3D story engine. Python sends a storyboard (list of shots) with
// window.load(shots), then asks for one frame at a time with window.frame(i, lt, t).
import * as THREE from '/studio/three.min.js';

const W = 1080, H = 1920;
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

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
function makeActor(spec, index) {
  const g = new THREE.Group();
  const shirt = mat(SHIRTS[spec.color] || Object.values(SHIRTS)[index % 9]);
  const skin = mat(SKINS[(spec.skin ?? index) % SKINS.length]);
  const jeans = mat(0x2b3a67), shoe = mat(0xf2f2f2);
  const body = new THREE.Group(); g.add(body);
  const legs = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.16 * s, 0.86, 0);
    p.add(mesh(new THREE.CylinderGeometry(0.115, 0.1, 0.8, 7), jeans, 0, -0.4, 0));
    p.add(mesh(new THREE.BoxGeometry(0.2, 0.12, 0.34), shoe, 0, -0.82, 0.06));
    body.add(p); return p;
  });
  const torso = new THREE.Group(); torso.position.y = 0.86; body.add(torso);
  torso.add(mesh(new THREE.CylinderGeometry(0.3, 0.27, 0.76, 8), shirt, 0, 0.38, 0));
  const arms = [-1, 1].map((s) => {
    const p = new THREE.Group(); p.position.set(0.38 * s, 0.68, 0);
    p.add(mesh(new THREE.CylinderGeometry(0.085, 0.075, 0.62, 6), shirt, 0, -0.31, 0));
    p.add(mesh(new THREE.IcosahedronGeometry(0.09, 0), skin, 0, -0.66, 0));
    torso.add(p); return p;
  });
  const head = new THREE.Group(); head.position.y = 1.04; torso.add(head);
  head.add(mesh(new THREE.IcosahedronGeometry(0.28, 1), skin));
  const hair = mesh(new THREE.SphereGeometry(0.295, 8, 5, 0, Math.PI * 2, 0, Math.PI * 0.52), mat(HAIR[index % HAIR.length]), 0, 0.03, -0.02);
  head.add(hair);
  [-1, 1].forEach((s) => head.add(mesh(new THREE.SphereGeometry(0.035, 6, 6), mat(0x111111), 0.1 * s, 0.03, 0.26)));
  head.add(mesh(new THREE.BoxGeometry(0.12, 0.025, 0.02), mat(0x5a2a22), 0, -0.1, 0.265));
  if (spec.tie) { torso.add(mesh(new THREE.BoxGeometry(0.1, 0.5, 0.03), mat(0xc0392b), 0, 0.42, 0.3)); torso.add(mesh(new THREE.BoxGeometry(0.34, 0.1, 0.05), mat(0xffffff), 0, 0.72, 0.27)); g.scale.setScalar(1.1); }
  let phone = null;
  if (spec.pose === 'phone') {
    phone = box(0.16, 0.3, 0.03, 0x111111, 0, -0.74, 0.06, { emissive: 0x9fd0ff, emissiveIntensity: 0.9 });
    arms[1].add(phone);
  }
  if (spec.float) { const f = label3d(spec.float.text, spec.float.color || '#ffffff', 0.8); f.position.y = 2.75; g.add(f); g.userData.float = f; }
  const face = { left: -1.1, right: 1.1, camera: 0, away: Math.PI }[spec.look || 'camera'] ?? 0;
  g.position.set(spec.x ?? 0, 0, spec.z ?? 0);
  g.rotation.y = face;
  g.userData = { ...g.userData, spec, body, torso, legs, arms, head, x0: spec.x ?? 0 };
  return g;
}

function poseActor(a, lt) {
  const { spec, body, torso, legs, arms, head, x0 } = a.userData;
  const breathe = Math.sin(lt * 2.2) * 0.012;
  body.position.y = breathe; torso.rotation.set(0, 0, 0); head.rotation.set(0, Math.sin(lt * 0.9) * 0.08, 0);
  legs.forEach((l) => l.rotation.set(0, 0, 0));
  arms.forEach((p, i) => p.rotation.set(0, 0, (i ? 1 : -1) * 0.1));
  switch (spec.pose) {
    case 'walk': {
      const s = Math.sin(lt * 7), dir = spec.look === 'left' ? -1 : 1;
      legs[0].rotation.x = s * 0.65; legs[1].rotation.x = -s * 0.65;
      arms[0].rotation.x = -s * 0.5; arms[1].rotation.x = s * 0.5;
      body.position.y = Math.abs(Math.cos(lt * 7)) * 0.05;
      a.position.x = x0 + dir * lt * 0.55; break;
    }
    case 'sit': case 'type':
      body.position.y = -0.38 + breathe; legs.forEach((l) => { l.rotation.x = -1.5; });
      if (spec.pose === 'type') arms.forEach((p, i) => { p.rotation.x = -1.15 + Math.sin(lt * 14 + i * 2) * 0.06; });
      else arms.forEach((p) => { p.rotation.x = -0.5; });
      break;
    case 'sad':
      torso.rotation.x = 0.22; head.rotation.x = 0.55; head.rotation.y = 0;
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * 0.04; }); break;
    case 'cheer':
      body.position.y = Math.abs(Math.sin(lt * 7)) * 0.22;
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * (2.6 + Math.sin(lt * 9) * 0.15); });
      head.rotation.x = -0.2; break;
    case 'phone':
      arms[1].rotation.x = -1.15; arms[1].rotation.z = -0.25; head.rotation.x = 0.32; head.rotation.y = 0.1; break;
    case 'point':
      arms[1].rotation.x = -1.45 + Math.sin(lt * 5) * 0.05; arms[1].rotation.z = 0.5; break;
    case 'panic':
      arms.forEach((p, i) => { p.rotation.z = (i ? 1 : -1) * 2.3; p.rotation.x = Math.sin(lt * 18 + i) * 0.25; });
      head.rotation.y = Math.sin(lt * 10) * 0.25; body.position.y = Math.abs(Math.sin(lt * 10)) * 0.05; break;
    case 'yell':
      torso.rotation.x = 0.28; head.rotation.x = -0.25 + Math.sin(lt * 22) * 0.06;
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
    const actors = (shot.actors || []).map((spec, i) => {
      const a = makeActor(spec, i); scene.add(a);
      if (spec.pose === 'sit') addProp(a, { type: 'bench', x: 0 }, updaters);
      if (spec.pose === 'type') { addProp(a, { type: 'desk', x: 0, state: spec.screen }, updaters); if (!spec.look) a.rotation.y = 0.75; }
      return a;
    });
    (shot.props || []).forEach((p) => addProp(scene, p, updaters));
    const xs = actors.filter((a) => a.userData.spec.pose !== 'walk').map((a) => a.position.x);
    const focus = xs.length ? xs.reduce((s, v) => s + v, 0) / xs.length : 0;
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
