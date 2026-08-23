const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function j(url, opts) { const r = await fetch(url, opts); return r.json(); }

// Self-scheduling loop: never two ticks in flight, even if a fetch runs long on a
// slow/high-latency link. /api/state is light and polled every tick (~500ms); the
// heavier panels (waterfall spectra + alerts) are polled at half that rate.
let tickCount = 0;

async function tick() {
  try {
    const s = await j('/api/state');
    $('presence').textContent = s.src === 'none' ? '–' : (s.presence ? 'PRESENT' : 'EMPTY');
    $('motion').textContent = s.src === 'none' ? '–' : (s.motion ? 'MOVING' : 'STILL');
    $('activity').textContent = s.activity ?? '–';
    $('srcbadge').textContent = s.src || '';
    $('calstale').hidden = !s.cal_stale;
    document.body.classList.toggle('present', !!s.presence);

    rvState = s;
    renderSense(await j('/api/sense'));

    if (tickCount % 2 === 0) {
      try {
        const m = await j('/api/mode');
        document.querySelectorAll('button[data-mode]').forEach(b =>
          b.classList.toggle('active', b.dataset.mode === m.mode));
      } catch (e) { /* older server without GET /api/mode - highlight stays off */ }
      const rows = await j('/api/waterfall?n=120');
      drawWaterfall(rows);
      drawSpectrogram(rows);
      const alerts = await j('/api/alerts?n=10');
      $('alerts').innerHTML = alerts.reverse().map(a =>
        `<li>${new Date(a.ts * 1000).toLocaleTimeString()} — ${esc(a.type)}</li>`).join('');
    }
    tickCount++;
  } finally {
    setTimeout(tick, 500);
  }
}

// Navy -> cyan -> yellow colormap. t in [0,1].
const WF_NAVY = [10, 26, 60];    // #0a1a3c
const WF_CYAN = [25, 184, 216];  // #19b8d8
const WF_YELLOW = [255, 216, 60]; // #ffd83c
function wfColorRGB(t) {
  t = Math.max(0, Math.min(1, t));
  let a, b, f;
  if (t < 0.5) { a = WF_NAVY; b = WF_CYAN; f = t / 0.5; }
  else { a = WF_CYAN; b = WF_YELLOW; f = (t - 0.5) / 0.5; }
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return [r, g, bl];
}
function wfColor(t) {
  const [r, g, bl] = wfColorRGB(t);
  return `rgb(${r},${g},${bl})`;
}

const WF_GUTTER = 58;   // left label gutter, px
const WF_TIMEBAND = 18; // bottom time-axis band, px
const WF_COLS = 120;    // matches /api/waterfall?n=120

// Offscreen pixel buffer (one texel per cell) + last-painted-row tracking, so an
// unchanged tick costs nothing and a changed tick costs one putImageData + one
// drawImage instead of thousands of fillRect calls.
let wfOff = null, wfOffCtx = null, wfOffRows = 0;
let wfLastTs;

function drawWaterfall(rows) {
  const last = rows.length ? rows[rows.length - 1] : null;
  const ts = last ? last.ts : null;
  if (ts === wfLastTs) return; // newest row unchanged since the last paint - skip the repaint
  wfLastTs = ts;

  const cv = $('waterfall'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);

  const plotX = WF_GUTTER;
  const plotW = cv.width - WF_GUTTER;
  const plotH = cv.height - WF_TIMEBAND;

  // Determine channel count from the latest row (dynamic per data row).
  const chans = last && last.channels ? last.channels.length : 0;

  // Plot area background (navy, i.e. t=0) so empty/zero rows still read as "calm", not blank.
  ctx.fillStyle = wfColor(0);
  ctx.fillRect(plotX, 0, plotW, plotH);

  if (rows.length && chans) {
    if (!wfOff || wfOffRows !== chans) {
      wfOff = document.createElement('canvas');
      wfOff.width = WF_COLS; wfOff.height = chans;
      wfOffCtx = wfOff.getContext('2d');
      wfOffRows = chans;
    }
    const img = wfOffCtx.createImageData(WF_COLS, chans);
    const data = img.data;
    const [bgR, bgG, bgB] = wfColorRGB(0);
    for (let p = 0; p < WF_COLS * chans; p++) {
      const o = p * 4;
      data[o] = bgR; data[o + 1] = bgG; data[o + 2] = bgB; data[o + 3] = 255;
    }
    rows.forEach((r, x) => {
      if (x >= WF_COLS) return;
      const vals = r.channels || [];
      vals.forEach((v, y) => {
        if (y >= chans) return; // guard against a row with more channels than the latest
        const t = Math.min(1, Math.sqrt(v / 0.8));
        const [cr, cg, cb] = wfColorRGB(t);
        const o = (y * WF_COLS + x) * 4;
        data[o] = cr; data[o + 1] = cg; data[o + 2] = cb; data[o + 3] = 255;
      });
    });
    wfOffCtx.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(wfOff, plotX, 0, plotW, plotH);
  }

  // Row labels (left gutter): "AP 1" .. "AP N-1", last row "LINK".
  ctx.font = '10px monospace';
  ctx.fillStyle = '#6b7690';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  if (chans) {
    const ch = plotH / chans;
    for (let y = 0; y < chans; y++) {
      const label = (y === chans - 1) ? 'LINK' : `AP ${y + 1}`;
      ctx.fillText(label, 2, y * ch + ch / 2);
    }
  }

  // Time axis (bottom band): "60s ago" at plot-left, "now" at plot-right.
  ctx.font = '10px monospace';
  ctx.fillStyle = '#6b7690';
  ctx.textBaseline = 'alphabetic';
  const timeY = cv.height - 5;
  ctx.textAlign = 'left';
  ctx.fillText('60s ago', plotX + 2, timeY);
  ctx.textAlign = 'right';
  ctx.fillText('now', cv.width - 2, timeY);
}

const SPEC_GUTTER = 58;    // left frequency-label gutter, px
const SPEC_RIGHT = 92;     // right band-annotation gutter, px
const SPEC_TIMEBAND = 18;  // bottom time-axis band, px
const SPEC_TOPPAD = 10;    // top padding, px - keeps the "2.0" tick label from clipping the canvas edge
const SPEC_FS_MAX = 2.0;   // Hz - Nyquist for 60 samples / 15 s window (cfg.window_seconds)
const SPEC_COLS = 120;     // matches /api/waterfall?n=120

let specOff = null, specOffCtx = null, specOffBins = 0;
let specLastTs;

function drawSpectrogram(rows) {
  // Bin count from the latest row carrying a spectrum; rows lacking one (old data
  // written before this feature, or a skipped inference) are simply skipped below.
  const specRows = rows.filter(r => Array.isArray(r.spectrum) && r.spectrum.length);
  const lastSpec = specRows.length ? specRows[specRows.length - 1] : null;
  const ts = lastSpec ? lastSpec.ts : null;
  if (ts === specLastTs) return; // newest spectrum row unchanged since the last paint - skip
  specLastTs = ts;

  const cv = $('spectrogram'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);

  const plotX = SPEC_GUTTER;
  const plotW = cv.width - SPEC_GUTTER - SPEC_RIGHT;
  const plotH = cv.height - SPEC_TIMEBAND - SPEC_TOPPAD;

  // Plot area background (navy, i.e. t=0) so windows with no motion still read as "calm".
  ctx.fillStyle = wfColor(0);
  ctx.fillRect(plotX, SPEC_TOPPAD, plotW, plotH);

  let bins = 0;
  if (specRows.length) {
    bins = lastSpec.spectrum.length; // 30
    if (!specOff || specOffBins !== bins) {
      specOff = document.createElement('canvas');
      specOff.width = SPEC_COLS; specOff.height = bins;
      specOffCtx = specOff.getContext('2d');
      specOffBins = bins;
    }

    // Per-row (per-frequency-bin) 95th-percentile normalization over the visible
    // 120-column window. Raw |rfft| magnitude has a 1/f tilt, so low bins always
    // dominate under one global scale and flatten contrast everywhere else. Scaling
    // each row against its OWN recent p95 instead makes every band show temporal
    // CHANGE: a walking burst pops out, a quiet floor goes dark, and a steady fan
    // line still reads as a steady stripe. Cheap: 30 rows x 120 values, redone every
    // redraw.
    const rowP95 = new Array(bins).fill(1e-6);
    for (let i = 0; i < bins; i++) {
      const vals = [];
      for (let x = 0; x < rows.length && x < SPEC_COLS; x++) {
        const spec = rows[x].spectrum;
        if (spec && i < spec.length) vals.push(spec[i]);
      }
      if (vals.length) {
        vals.sort((a, b) => a - b);
        const p95 = vals[Math.min(vals.length - 1, Math.floor(0.95 * vals.length))];
        rowP95[i] = Math.max(p95, 1e-6);
      }
    }

    const img = specOffCtx.createImageData(SPEC_COLS, bins);
    const data = img.data;
    const [bgR, bgG, bgB] = wfColorRGB(0);
    for (let p = 0; p < SPEC_COLS * bins; p++) {
      const o = p * 4;
      data[o] = bgR; data[o + 1] = bgG; data[o + 2] = bgB; data[o + 3] = 255;
    }
    rows.forEach((r, x) => {
      if (x >= SPEC_COLS) return;
      const spec = r.spectrum;
      if (!spec) return; // old row without a spectrum - graceful skip
      spec.forEach((v, i) => {
        if (i >= bins) return;
        const t = Math.min(1, Math.sqrt(v / (1.4 * rowP95[i])));
        const [cr, cg, cb] = wfColorRGB(t);
        const row = bins - 1 - i; // bin 0 (lowest freq) at the bottom
        const o = (row * SPEC_COLS + x) * 4;
        data[o] = cr; data[o + 1] = cg; data[o + 2] = cb; data[o + 3] = 255;
      });
    });
    specOffCtx.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(specOff, plotX, SPEC_TOPPAD, plotW, plotH);
  }

  // Walking-band highlight: 0.5-2.0 Hz, i.e. the top 75% of the 0-2.0 Hz (Nyquist) axis.
  const bandTopY = SPEC_TOPPAD;                                    // 2.0 Hz
  const bandBottomY = SPEC_TOPPAD + plotH * (1 - 0.5 / SPEC_FS_MAX); // 0.5 Hz

  // Subtle dashed guide line at the band's 0.5 Hz floor.
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.setLineDash([4, 3]);
  ctx.beginPath();
  ctx.moveTo(plotX, bandBottomY);
  ctx.lineTo(plotX + plotW, bandBottomY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Tinted edge strip along the right side of the plot marking the band.
  ctx.fillStyle = 'rgba(122, 199, 255, 0.16)';
  ctx.fillRect(plotX + plotW - 5, bandTopY, 5, bandBottomY - bandTopY);

  // Right-gutter bracket + "human motion band" label.
  const bx = plotX + plotW + 10;
  ctx.strokeStyle = '#3a4666';
  ctx.beginPath();
  ctx.moveTo(bx, bandTopY); ctx.lineTo(bx + 5, bandTopY);
  ctx.lineTo(bx + 5, bandBottomY); ctx.lineTo(bx, bandBottomY);
  ctx.stroke();
  ctx.font = '9px monospace';
  ctx.fillStyle = '#7ac7ff';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  const midY = (bandTopY + bandBottomY) / 2;
  ctx.fillText('human', bx + 9, midY - 8);
  ctx.fillText('motion', bx + 9, midY + 2);
  ctx.fillText('band', bx + 9, midY + 12);

  // Frequency axis ticks (left gutter): 0.5 / 1.0 / 1.5 / 2.0 Hz, low at bottom.
  ctx.font = '10px monospace';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  [0.5, 1.0, 1.5, 2.0].forEach(f => {
    const y = SPEC_TOPPAD + plotH * (1 - f / SPEC_FS_MAX);
    ctx.fillStyle = '#6b7690';
    ctx.fillText(f.toFixed(1), plotX - 6, y);
    ctx.strokeStyle = '#2a3550';
    ctx.beginPath(); ctx.moveTo(plotX - 3, y); ctx.lineTo(plotX, y); ctx.stroke();
  });

  // Time axis (bottom band): "60s ago" at plot-left, "now" at plot-right.
  ctx.font = '10px monospace';
  ctx.fillStyle = '#6b7690';
  ctx.textBaseline = 'alphabetic';
  const timeY = cv.height - 5;
  ctx.textAlign = 'left';
  ctx.fillText('60s ago', plotX + 2, timeY);
  ctx.textAlign = 'right';
  ctx.fillText('now', plotX + plotW - 2, timeY);
}

// ---------------- RF sensing console ----------------
// All values shown are real detector internals (aura/brain/rfsense): per-link
// votes/thresholds, the fused vote fractions, and CUSUM change-point counts.
// The radar is deliberately abstract - RSSI carries no position information.
let rvState = {};          // latest /api/state (for the radar)
let rvDetail = null;       // latest /api/sense payload
let rvLastTs = null;       // dedup: ticker fires once per new inference
let rvMbandMax = 1e-6, rvBbandMax = 1e-6;  // self-scaling meter ceilings (slow decay)

function renderSense(d) {
  rvDetail = (d && d.links) ? d : null;
  const stateEl = $('rv-state');
  if (!rvDetail) {
    stateEl.textContent = '—'; stateEl.className = 'rv-state';
    $('rv-links').innerHTML = '';
    return;
  }
  const st = d.state || {};
  const level = st.motion ? 'active' : (st.presence ? 'present_still' : 'absent');
  stateEl.textContent = { absent: 'ABSENT', present_still: 'PRESENT · STILL', active: 'ACTIVE' }[level];
  stateEl.className = 'rv-state ' + level;
  drawGauge(st.confidence ?? 0);

  rvMbandMax = Math.max(d.fused_band_energy, rvMbandMax * 0.995, 1e-6);
  rvBbandMax = Math.max(d.fused_breathing_energy, rvBbandMax * 0.995, 1e-6);
  $('rv-mband').style.width = Math.round(100 * Math.min(1, d.fused_band_energy / rvMbandMax)) + '%';
  $('rv-bband').style.width = Math.round(100 * Math.min(1, d.fused_breathing_energy / rvBbandMax)) + '%';

  $('rv-links').innerHTML = d.links.map(l => {
    const varFill = Math.min(100, 50 * l.variance / Math.max(l.var_thresh, 1e-9));
    const bandFill = Math.min(100, 50 * l.band_energy / Math.max(l.motion_thresh, 1e-9));
    return `<div class="rv-linkcard">
      <span class="id">${esc(l.id === '__link__' ? 'LINK' : l.id)}</span><span class="rssi">${esc(l.rssi)} dBm</span>
      <span class="rv-vote ${esc(l.vote)}">${esc(l.vote.replace('_', ' '))}</span>
      <div class="k">variance ${esc(l.variance)} / thr ${esc(l.var_thresh)}</div>
      <div class="rv-minibar"><div class="fill" style="width:${varFill}%"></div><div class="th" style="left:50%"></div></div>
      <div class="k">motion band ${esc(l.band_energy)} / thr ${esc(l.motion_thresh)}</div>
      <div class="rv-minibar"><div class="fill" style="width:${bandFill}%"></div><div class="th" style="left:50%"></div></div>
      <div class="k">weight ${esc(l.weight)} · conf ${esc(l.confidence)}</div>
    </div>`;
  }).join('');

  if (d.ts !== rvLastTs) {
    rvLastTs = d.ts;
    const events = d.links.filter(l => l.change_points > 0);
    if (events.length) {
      const t = new Date(d.ts * 1000).toLocaleTimeString();
      const li = document.createElement('li');
      li.textContent = `${t} — ` + events.map(l =>
        `${l.id === '__link__' ? 'LINK' : l.id}: ${l.change_points} change-point${l.change_points > 1 ? 's' : ''}`).join(', ');
      const ul = $('rv-ticker');
      ul.insertBefore(li, ul.firstChild);
      while (ul.children.length > 8) ul.removeChild(ul.lastChild);
    }
  }
}

function drawGauge(conf) {
  const cv = $('rv-gauge'), ctx = cv.getContext('2d');
  const cx = cv.width / 2, cy = cv.height - 8, r = 62;
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.lineWidth = 10; ctx.lineCap = 'round';
  ctx.strokeStyle = '#0a1a3c';
  ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI); ctx.stroke();
  ctx.strokeStyle = wfColor(conf);
  ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, Math.PI * (1 + Math.max(0, Math.min(1, conf)))); ctx.stroke();
  ctx.font = '16px monospace'; ctx.fillStyle = '#dce3f0';
  ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.fillText(Math.round(conf * 100) + '%', cx, cy - 6);
}

// ---------------- Room view ----------------
// Top-down sketch of the real radio paths. Geometry is schematic (device spots
// are fixed), but everything that MOVES is measurement-driven: per-path glow =
// that channel's live variance/threshold ratio, rings = CUSUM change-points,
// lens glow = fused motion-band energy, and the presence marker drifts toward
// the disturbance-weighted centroid of the over-threshold paths. No position
// is measured; the marker is a signal-derived hint, and the UI says so.
const ROOM_PAD = 10;
let roomBlob = null;        // smoothed marker position {x, y}
let roomRipples = [];       // [{x, y, r, alpha}]
let roomRippleTs = null;    // last inference ts that spawned ripples
let roomLensMax = 1e-6;     // self-scaling ceiling for lens glow (slow decay)

function roomGeom(cv) {
  const w = cv.width, h = cv.height;
  const board = { x: ROOM_PAD + 0.10 * w, y: h - ROOM_PAD - 0.12 * h };
  const phone = { x: w - ROOM_PAD - 0.10 * w, y: ROOM_PAD + 0.14 * h };
  return { w, h, board, phone };
}

// One endpoint per AP channel: antenna glyphs spread along the top wall
// (surrounding networks live outside the room; direction is schematic).
function roomApEnd(g, idx, count) {
  const f = (idx + 1) / (count + 1);
  return { x: ROOM_PAD + 14 + f * (g.w - 2 * ROOM_PAD - 28), y: ROOM_PAD + 4 };
}

function drawDevice(ctx, p, label, on) {
  ctx.fillStyle = on ? '#19b8d8' : '#3a4666';
  ctx.fillRect(p.x - 5, p.y - 5, 10, 10);
  ctx.font = '9px monospace';
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.fillStyle = '#6b7690';
  ctx.fillText(label, p.x, p.y + 8);
}

function drawRoom() {
  const cv = $('rv-room'), ctx = cv.getContext('2d');
  const g = roomGeom(cv);
  // translucent repaint instead of clear -> the marker leaves a fading trail
  ctx.fillStyle = 'rgba(10, 16, 32, 0.13)';
  ctx.fillRect(0, 0, g.w, g.h);

  // room outline
  ctx.strokeStyle = 'rgba(122, 199, 255, 0.22)';
  ctx.lineWidth = 1;
  ctx.strokeRect(ROOM_PAD, ROOM_PAD, g.w - 2 * ROOM_PAD, g.h - 2 * ROOM_PAD);

  const d = rvDetail;
  const links = d ? d.links : [];
  const apChannels = links.filter(l => l.id !== '__link__');
  const linkCh = links.find(l => l.id === '__link__');

  // disturbance ratio per channel: how far past its calibrated thresholds it is
  const ratio = l => Math.max(l.variance / Math.max(l.var_thresh, 1e-9),
                              l.band_energy / Math.max(l.motion_thresh, 1e-9));

  // AP paths: thin lines board -> wall antennas, brightening with live disturbance
  const anchors = [];   // [{x, y, w}] disturbance-weighted anchor candidates
  apChannels.forEach((l, i) => {
    const end = roomApEnd(g, i, apChannels.length);
    const r = Math.min(2, ratio(l));
    ctx.strokeStyle = `rgba(25, 184, 216, ${0.10 + 0.35 * Math.min(1, r)})`;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(g.board.x, g.board.y); ctx.lineTo(end.x, end.y); ctx.stroke();
    ctx.fillStyle = '#3a4666';
    ctx.fillRect(end.x - 2, end.y - 2, 4, 4);
    ctx.font = '8px monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillStyle = '#4a5673';
    ctx.fillText(l.id.slice(0, 4), end.x, end.y + 4);
    if (r > 0.5) anchors.push({ x: (g.board.x + end.x) / 2, y: (g.board.y + end.y) / 2, w: r });
  });

  // Fresnel lens on the main sensing link (board <-> phone): glow follows the
  // fused motion-band energy, self-scaled like the meter bars.
  if (d) roomLensMax = Math.max(d.fused_band_energy, roomLensMax * 0.995, 1e-6);
  const lens = d ? Math.min(1, d.fused_band_energy / roomLensMax) : 0;
  const mx = (g.board.x + g.phone.x) / 2, my = (g.board.y + g.phone.y) / 2;
  const dx = g.phone.x - g.board.x, dy = g.phone.y - g.board.y;
  const L = Math.hypot(dx, dy), ang = Math.atan2(dy, dx);
  ctx.save();
  // keep the lens and its glow inside the room outline
  ctx.beginPath();
  ctx.rect(ROOM_PAD, ROOM_PAD, g.w - 2 * ROOM_PAD, g.h - 2 * ROOM_PAD);
  ctx.clip();
  ctx.translate(mx, my); ctx.rotate(ang);
  ctx.strokeStyle = `rgba(25, 184, 216, ${0.18 + 0.5 * lens})`;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.ellipse(0, 0, L / 2, L / 8, 0, 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([3, 4]);
  ctx.strokeStyle = `rgba(25, 184, 216, ${0.25 + 0.45 * lens})`;
  ctx.beginPath(); ctx.moveTo(-L / 2, 0); ctx.lineTo(L / 2, 0); ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
  if (linkCh && ratio(linkCh) > 0.5) anchors.push({ x: mx, y: my, w: ratio(linkCh) });

  drawDevice(ctx, g.board, 'board', true);
  drawDevice(ctx, g.phone, 'phone (hotspot)', true);

  // rings on real CUSUM change-points, once per new inference
  if (d && d.ts !== roomRippleTs) {
    roomRippleTs = d.ts;
    links.forEach((l, i) => {
      if (l.change_points > 0) {
        const p = l.id === '__link__' ? { x: mx, y: my }
          : (() => { const e = roomApEnd(g, apChannels.indexOf(l), apChannels.length);
                     return { x: (g.board.x + e.x) / 2, y: (g.board.y + e.y) / 2 }; })();
        roomRipples.push({ x: p.x, y: p.y, r: 4, alpha: 0.7 });
      }
    });
  }
  roomRipples = roomRipples.filter(rp => rp.alpha > 0.02);
  roomRipples.forEach(rp => {
    ctx.strokeStyle = `rgba(255, 216, 60, ${rp.alpha})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(rp.x, rp.y, rp.r, 0, 2 * Math.PI); ctx.stroke();
    rp.r += 1.4; rp.alpha *= 0.94;
  });

  // presence marker: disturbance-weighted centroid of the over-threshold paths,
  // eased for legibility; rests on the lens centre when nothing distinguishes.
  const s = rvState;
  if (s && s.presence) {
    let tx = mx, ty = my;
    const wsum = anchors.reduce((a, c) => a + c.w, 0);
    if (wsum > 0) {
      tx = anchors.reduce((a, c) => a + c.x * c.w, 0) / wsum;
      ty = anchors.reduce((a, c) => a + c.y * c.w, 0) / wsum;
    }
    if (!roomBlob) roomBlob = { x: tx, y: ty };
    roomBlob.x += (tx - roomBlob.x) * 0.06;
    roomBlob.y += (ty - roomBlob.y) * 0.06;
    const act = Math.max(0, Math.min(100, s.activity ?? 0));
    const pulse = s.motion ? 1 + 0.12 * Math.sin(performance.now() / 180) : 1;
    const blobR = (10 + 0.24 * act) * pulse;
    const col = s.motion ? '122, 255, 196' : '255, 216, 60';
    const grad = ctx.createRadialGradient(roomBlob.x, roomBlob.y, 2, roomBlob.x, roomBlob.y, blobR);
    grad.addColorStop(0, `rgba(${col}, 0.85)`);
    grad.addColorStop(1, `rgba(${col}, 0)`);
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(roomBlob.x, roomBlob.y, blobR, 0, 2 * Math.PI); ctx.fill();
    // zone hook: when zone sensing lands, the brain adds state.zone
    if (s.zone) {
      ctx.font = '10px monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
      ctx.fillStyle = '#dce3f0';
      ctx.fillText(s.zone, roomBlob.x, roomBlob.y - blobR - 3);
    }
  } else {
    roomBlob = null;
  }
  requestAnimationFrame(drawRoom);
}
requestAnimationFrame(drawRoom);

document.querySelectorAll('button[data-mode]').forEach(b =>
  b.onclick = async () => {
    await j('/api/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: b.dataset.mode }) });
    document.querySelectorAll('button[data-mode]').forEach(x =>
      x.classList.toggle('active', x === b));
  });
$('cal').onclick = async () => {
  alert('Learn my room: the hotspot phone is the far end of the sensor — leave it in THIS room, ' +
    'untouched, and leave the room without it. Aura learns "empty" for 10 minutes. ' +
    'Keep this page open; it will ask you to walk afterwards.');
  await j('/api/calibrate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase: 'empty', minutes: 10 }) });
  setTimeout(async () => {
    alert('Empty phase done. Come back in (phone stays where it is), start walking around the room — ' +
      'crossing between this device and the phone — then press OK and keep walking for 5 minutes.');
    await j('/api/calibrate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'walk', minutes: 5 }) });
    setTimeout(() => alert('Calibration captured. Restart the brain to load it: ' +
      'sudo systemctl restart aura-brain'), 5.3 * 60 * 1000);
  }, 10.3 * 60 * 1000);
};
tick();
