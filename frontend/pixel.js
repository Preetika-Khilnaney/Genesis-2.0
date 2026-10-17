/* Salvage pixel art: original, generated in the browser (no image files, no network).
   Every sprite is drawn on a small canvas and scaled up with image-rendering: pixelated.
   Usage in HTML: <canvas data-pixel="skyline"></canvas>  (see SPRITES below)            */

const PAL = {
  d: '#2B3A55', // outline
  w: '#F6F8FC', // white
  g: '#C8D2E0', // light grey
  G: '#8E9BB0', // mid grey
  b: '#5EC8F2', // sky blue
  B: '#2F7FD1', // deep blue
  t: '#3DB5A6', // teal
  T: '#9FE3D8', // light teal
  o: '#F28C38', // orange
  y: '#FFD15C', // yellow
  r: '#FF6B3D', // red
  p: '#8C7CF0', // violet
  P: '#D9D3FF', // light violet
  k: '#F2B8A0', // peach
  l: '#7CC46B', // leaf
  L: '#4E9A45', // dark leaf
  n: '#8A5A3C', // trunk
};

/* ---------- tiny seeded RNG so the skyline is the same on every load ---------- */
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function grid(rows) {
  const w = Math.max(...rows.map(r => r.length));
  return rows.map(r => r.padEnd(w, '.'));
}

function drawGrid(ctx, rows, ox = 0, oy = 0, pal = PAL) {
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const c = row[x];
      if (c === '.' || c === ' ') continue;
      ctx.fillStyle = pal[c] || c;
      ctx.fillRect(ox + x, oy + y, 1, 1);
    }
  });
}

/* ---------- sprites (hand-drawn, original) ---------- */
const SHIP = grid([
  '..............dddddddd',
  '............ddwwwwwwwwdd',
  '..........ddwwwwwbbbbwwwdd',
  '...dd....dwwwwwwwbbbbbbwwwdd',
  '..dttd..dwwwwwwwwwbbbbbwwwwwdd',
  'yrdttdddwwwwwwwwwwwwwwwwwwwwwwdd',
  'yyrddwwwoooooooooooooooooowwwwwwdd',
  'yrdttdggggggggggggggggggggggggggdd',
  '..dttd..dggggggggggggggggggggggdd',
  '...dd....dddddddddddddddddddddd',
]);

const ICONS = {
  floppy: grid([
    'dddddddddddddd',
    'dBBBwwwwwwwBBBd',
    'dBBBwwwwwdwBBBBd',
    'dBBBwwwwwdwBBBBd',
    'dBBBwwwwwwwBBBBd',
    'dBBBBBBBBBBBBBBd',
    'dBBwwwwwwwwwwBBd',
    'dBBwggggggggwBBd',
    'dBBwwwwwwwwwwBBd',
    'dBBwggggggggwBBd',
    'dBBwwwwwwwwwwBBd',
    'dBBwggggggggwBBd',
    'dBBwwwwwwwwwwBBd',
    'dddddddddddddddd',
  ]),
  crt: grid([
    '.dddddddddddddd',
    '.dggggggggggggd',
    '.dgddddddddddgd',
    '.dgdttdddddddgd',
    '.dgddtttdddddgd',
    '.dgddddddtdddgd',
    '.dgdddtttttddgd',
    '.dgddddddddddgd',
    '.dggggggggggggd',
    '.dgggggggggorgd',
    '.dddddddddddddd',
    '......dggd',
    '....dddddddd',
  ]),
  cartridge: grid([
    '..dddddddddddd',
    '..dppppppppppd',
    '..dpwwwwwwwwpd',
    '..dpwddddddwpd',
    '..dpwwwwwwwwpd',
    '..dpwddddwwwpd',
    '..dpwwwwwwwwpd',
    '..dppppppppppd',
    '..dppppppppppd',
    '..dppppppppppd',
    '..dpypypypyppd',
    '..dddddddddddd',
  ]),
  doc: grid([
    '..ddddddddd',
    '..dwwwwwwwdd',
    '..dwwwwwwwdwd',
    '..dwddddwwdddd',
    '..dwwwwwwwwwwd',
    '..dwdddddddwwd',
    '..dwwwwwwwwwwd',
    '..dwddddddwwwd',
    '..dwwwwwwwwwwd',
    '..dwdddddddwwd',
    '..dwwwwwwwwwwd',
    '..dwddddwwwwwd',
    '..dwwwwwwwwwwd',
    '..dddddddddddd',
  ]),
  cassette: grid([
    'dddddddddddddddd',
    'doooooooooooooood',
    'dowwwwwwwwwwwwod',
    'dowddwwwwwwddwod',
    'dowdgdwwwwdgdwod',
    'dowddwwwwwwddwod',
    'dowwwwwwwwwwwwod',
    'doooooooooooooood',
    'doooddddddddoood',
    'dooddggggggddood',
    'dddddddddddddddd',
  ]),
  crate: grid([
    'dddddddddddddddd',
    'dyyyyyyyyyyyyyyd',
    'dddddddddddddddd',
    'dyyyyyddddyyyyyd',
    'dyyyyydGGdyyyyyd',
    'dyyyyyddddyyyyyd',
    'dyyyyyyyyyyyyyyd',
    'dyyddyyyyyyddyyd',
    'dyyyyyyyyyyyyyyd',
    'dyyyyyyyyyyyyyyd',
    'dddddddddddddddd',
  ]),
};

function iconSheet() {            // spreadsheet grid
  const r = [];
  for (let y = 0; y < 13; y++) {
    let row = '';
    for (let x = 0; x < 16; x++) {
      const edge = x === 0 || x === 15 || y === 0 || y === 12;
      const line = x % 5 === 0 || y % 3 === 0;
      row += edge ? 'd' : y < 3 ? 'L' : line ? 'g' : 'w';
    }
    r.push(row);
  }
  return r;
}

function iconReel() {             // tape reel
  const r = [];
  const N = 16, c = 7.5;
  for (let y = 0; y < N; y++) {
    let row = '';
    for (let x = 0; x < N; x++) {
      const d = Math.hypot(x - c, y - c);
      const a = Math.atan2(y - c, x - c);
      const spoke = d > 2 && d < 5.4 && Math.abs(Math.sin(a * 1.5)) < 0.32;
      row += d > 7.6 ? '.' : d > 6.6 ? 'd' : d < 1.4 ? 'd' : d < 2.2 ? 'w' : spoke ? 'G' : d < 5.6 ? 'B' : 'b';
    }
    r.push(row);
  }
  return r;
}

/* ---------- scenes ---------- */
function skyline(ctx, W, H, seed = 7) {
  const R = rng(seed);
  // sky: soft vertical bands (pixel-style gradient)
  const sky = ['#EAF4FD', '#E1EFFC', '#D6EAFB', '#CBE4FA', '#C0DEF8'];
  const band = Math.ceil((H * 0.62) / sky.length);
  sky.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(0, i * band, W, band); });
  // clouds
  ctx.fillStyle = '#F7FBFF';
  for (let i = 0; i < 5; i++) {
    const cx = Math.floor(R() * W), cy = 4 + Math.floor(R() * H * 0.22), w = 10 + Math.floor(R() * 16);
    ctx.fillRect(cx, cy, w, 2); ctx.fillRect(cx + 2, cy - 1, w - 5, 1); ctx.fillRect(cx + 4, cy - 2, w - 10, 1);
  }
  const horizon = Math.floor(H * 0.66);
  // three building layers, far to near
  const layers = [
    { c: '#BED8F1', win: null, min: 0.20, max: 0.55, wmin: 6, wmax: 14 },
    { c: '#A3C6EA', win: '#C9E0F6', min: 0.14, max: 0.42, wmin: 5, wmax: 11 },
    { c: '#7FA9DA', win: '#D7E8FA', min: 0.10, max: 0.34, wmin: 4, wmax: 9 },
  ];
  layers.forEach((L, li) => {
    let x = -Math.floor(R() * 6);
    while (x < W) {
      const bw = L.wmin + Math.floor(R() * (L.wmax - L.wmin));
      const bh = Math.floor(H * (L.min + R() * (L.max - L.min)));
      const top = horizon - bh;
      ctx.fillStyle = L.c;
      ctx.fillRect(x, top, bw, bh);
      if (R() < 0.35) ctx.fillRect(x + Math.floor(bw / 2), top - 3 - Math.floor(R() * 5), 1, 6);   // antenna
      if (R() < 0.25 && bw > 6) ctx.fillRect(x + 1, top - 2, bw - 2, 2);                             // roof step
      if (L.win) {
        ctx.fillStyle = L.win;
        for (let wy = top + 2; wy < horizon - 2; wy += 3)
          for (let wx = x + 1; wx < x + bw - 1; wx += 2)
            if (R() < 0.55) ctx.fillRect(wx, wy, 1, 1);
      }
      x += bw + (li === 0 ? 0 : Math.floor(R() * 3));
    }
  });
  // a needle tower (generic) on the mid layer
  const tx = Math.floor(W * 0.30);
  ctx.fillStyle = '#8DB4E0';
  ctx.fillRect(tx, horizon - Math.floor(H * 0.52), 2, Math.floor(H * 0.52));
  ctx.fillRect(tx - 4, horizon - Math.floor(H * 0.40), 10, 3);
  ctx.fillRect(tx - 2, horizon - Math.floor(H * 0.43), 6, 2);
  ctx.fillRect(tx + 0, horizon - Math.floor(H * 0.60), 1, 6);
  // water
  ctx.fillStyle = '#BFE2F6'; ctx.fillRect(0, horizon, W, H - horizon);
  ctx.fillStyle = '#E9F6FD';
  for (let i = 0; i < W * 0.6; i++) {
    const wx = Math.floor(R() * W), wy = horizon + 1 + Math.floor(R() * (H - horizon - 8));
    ctx.fillRect(wx, wy, 2 + Math.floor(R() * 4), 1);
  }
  // promenade + railing
  const ground = H - 6;
  ctx.fillStyle = '#9AA6BC'; ctx.fillRect(0, ground, W, 6);
  ctx.fillStyle = '#7C889E'; ctx.fillRect(0, ground, W, 1);
  ctx.fillStyle = '#5B6B86';
  ctx.fillRect(0, ground - 7, W, 1); ctx.fillRect(0, ground - 4, W, 1);
  for (let x = 2; x < W; x += 12) ctx.fillRect(x, ground - 8, 1, 8);
  // a generic tree on the left
  const trx = W - 28, trg = ground;
  ctx.fillStyle = PAL.n; ctx.fillRect(trx + 6, trg - 16, 2, 16);
  const blob = [[3, 0, 10], [1, 1, 14], [0, 2, 16], [0, 3, 16], [1, 4, 14], [0, 5, 16], [2, 6, 12], [4, 7, 8]];
  blob.forEach(([bx, by, bw]) => { ctx.fillStyle = PAL.l; ctx.fillRect(trx + bx - 1, trg - 26 + by, bw, 1); });
  ctx.fillStyle = PAL.L;
  [[2, 4], [5, 6], [10, 3], [12, 5], [7, 2]].forEach(([a, b]) => ctx.fillRect(trx + a, trg - 26 + b, 2, 1));
  // the ship, cruising high
  if (W < 300) drawGrid(ctx, SHIP, Math.floor(W * 0.56), Math.floor(H * 0.12));
}

function pipes(ctx, W, H) {
  ctx.fillStyle = '#FFF8E6'; ctx.fillRect(0, 0, W, H);
  const tube = (x, y, len, vertical, c1, c2, c3) => {
    for (let i = 0; i < len; i++) {
      const [px, py] = vertical ? [x, y + i] : [x + i, y];
      [c1, c2, c2, c3].forEach((c, k) => {
        ctx.fillStyle = c;
        vertical ? ctx.fillRect(px + k, py, 1, 1) : ctx.fillRect(px, py + k, 1, 1);
      });
    }
  };
  const grey = ['#E9EEF5', '#B9C4D4', '#7D8AA1'];
  const teal = ['#C9F2EB', '#6FD0C1', '#2E9B8C'];
  const orange = ['#FFE0C2', '#F6A35E', '#C96A1F'];
  tube(0, 8, W, false, ...grey);
  tube(0, H - 14, W, false, ...grey);
  tube(10, 8, H - 18, true, ...grey);
  tube(W - 16, 8, H - 18, true, ...grey);
  tube(14, Math.floor(H / 2) - 2, W - 30, false, ...teal);           // the glowing tube
  tube(Math.floor(W / 2), 12, Math.floor(H / 2) - 14, true, ...orange);
  // joints
  ctx.fillStyle = '#5B6B86';
  [[9, 7], [W - 17, 7], [9, H - 15], [W - 17, H - 15], [Math.floor(W / 2) - 1, Math.floor(H / 2) - 3]]
    .forEach(([x, y]) => ctx.fillRect(x, y, 6, 6));
  // valve wheel
  const vx = Math.floor(W * 0.25), vy = Math.floor(H / 2) - 9;
  ctx.fillStyle = '#E2513B';
  for (let a = 0; a < 24; a++) {
    const t = (a / 24) * Math.PI * 2;
    ctx.fillRect(vx + Math.round(Math.cos(t) * 5), vy + Math.round(Math.sin(t) * 5), 1, 1);
  }
  ctx.fillRect(vx - 5, vy, 11, 1); ctx.fillRect(vx, vy - 5, 1, 11);
  // gauge
  const gx = Math.floor(W * 0.74), gy = Math.floor(H * 0.70);
  ctx.fillStyle = '#2B3A55'; ctx.fillRect(gx - 5, gy - 5, 11, 11);
  ctx.fillStyle = '#FFFFFF'; ctx.fillRect(gx - 4, gy - 4, 9, 9);
  ctx.fillStyle = '#E2513B'; ctx.fillRect(gx, gy, 1, 1); ctx.fillRect(gx + 1, gy - 1, 1, 1); ctx.fillRect(gx + 2, gy - 2, 1, 1);
  ctx.fillStyle = '#7CC46B'; ctx.fillRect(gx - 3, gy + 3, 7, 1);
  // drips of data: little bits flowing in the teal tube
  ctx.fillStyle = '#FFFFFF';
  for (let x = 18; x < W - 20; x += 7) ctx.fillRect(x, Math.floor(H / 2), 2, 1);
}

function stars(ctx, W, H) {        // small night-free "space" tile in light tones
  ctx.fillStyle = '#EEF0FF'; ctx.fillRect(0, 0, W, H);
  const R = rng(3);
  for (let i = 0; i < W * H * 0.012; i++) {
    ctx.fillStyle = R() < 0.5 ? '#C6CBF5' : '#AEB6F0';
    ctx.fillRect(Math.floor(R() * W), Math.floor(R() * H), 1, 1);
  }
  // ringed planet (generic)
  const cx = Math.floor(W * 0.24), cy = Math.floor(H * 0.32), r = 8;
  for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++)
    if (x * x + y * y <= r * r) { ctx.fillStyle = (x + y) < -4 ? '#FFE3B3' : '#F6C77E'; ctx.fillRect(cx + x, cy + y, 1, 1); }
  ctx.fillStyle = '#C96A1F';
  for (let x = -14; x <= 14; x++) ctx.fillRect(cx + x, cy + Math.round(x * 0.18), 1, 1);
  drawGrid(ctx, SHIP, Math.floor(W * 0.30), Math.floor(H * 0.58));
}

/* ---------- registry ---------- */
const SPRITES = {
  skyline: { w: 200, h: 168, draw: (c, w, h) => skyline(c, w, h) },
  skylineWide: { w: 420, h: 72, draw: (c, w, h) => skyline(c, w, h, 11) },
  ship: { w: 34, h: 10, draw: c => drawGrid(c, SHIP) },
  space: { w: 96, h: 96, draw: (c, w, h) => stars(c, w, h) },
  pipes: { w: 96, h: 64, draw: (c, w, h) => pipes(c, w, h) },
  floppy: { w: 16, h: 14, draw: c => drawGrid(c, ICONS.floppy) },
  crt: { w: 16, h: 13, draw: c => drawGrid(c, ICONS.crt) },
  cartridge: { w: 16, h: 12, draw: c => drawGrid(c, ICONS.cartridge) },
  doc: { w: 16, h: 14, draw: c => drawGrid(c, ICONS.doc) },
  cassette: { w: 17, h: 11, draw: c => drawGrid(c, ICONS.cassette) },
  crate: { w: 16, h: 11, draw: c => drawGrid(c, ICONS.crate) },
  sheet: { w: 16, h: 13, draw: c => drawGrid(c, iconSheet()) },
  reel: { w: 16, h: 16, draw: c => drawGrid(c, iconReel()) },
};

export function paint(root = document) {
  root.querySelectorAll('canvas[data-pixel]').forEach(cv => {
    const s = SPRITES[cv.dataset.pixel];
    if (!s) return;
    cv.width = s.w; cv.height = s.h;
    const ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    s.draw(ctx, s.w, s.h);
  });
}

paint();
