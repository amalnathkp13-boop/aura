const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function j(url, opts) { const r = await fetch(url, opts); return r.json(); }

async function tick() {
  const s = await j('/api/state');
  $('presence').textContent = s.src === 'none' ? '–' : (s.presence ? 'PRESENT' : 'EMPTY');
  $('motion').textContent = s.src === 'none' ? '–' : (s.motion ? 'MOVING' : 'STILL');
  $('activity').textContent = s.activity ?? '–';
  $('srcbadge').textContent = s.src || '';
  document.body.classList.toggle('present', !!s.presence);
  const rows = await j('/api/waterfall?n=120');
  drawWaterfall(rows);
  drawSpectrogram(rows);
  const alerts = await j('/api/alerts?n=10');
  $('alerts').innerHTML = alerts.reverse().map(a =>
    `<li>${new Date(a.ts * 1000).toLocaleTimeString()} — ${esc(a.type)}</li>`).join('');
}

// Navy -> cyan -> yellow colormap. t in [0,1].
const WF_NAVY = [10, 26, 60];    // #0a1a3c
const WF_CYAN = [25, 184, 216];  // #19b8d8
const WF_YELLOW = [255, 216, 60]; // #ffd83c
function wfColor(t) {
  t = Math.max(0, Math.min(1, t));
  let a, b, f;
  if (t < 0.5) { a = WF_NAVY; b = WF_CYAN; f = t / 0.5; }
  else { a = WF_CYAN; b = WF_YELLOW; f = (t - 0.5) / 0.5; }
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

const WF_GUTTER = 58;   // left label gutter, px
const WF_TIMEBAND = 18; // bottom time-axis band, px

function drawWaterfall(rows) {
  const cv = $('waterfall'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);

  const plotX = WF_GUTTER;
  const plotW = cv.width - WF_GUTTER;
  const plotH = cv.height - WF_TIMEBAND;

  // Determine channel count from the latest row (dynamic per data row).
  const last = rows.length ? rows[rows.length - 1] : null;
  const chans = last && last.channels ? last.channels.length : 0;

  // Plot area background (navy, i.e. t=0) so empty/zero rows still read as "calm", not blank.
  ctx.fillStyle = wfColor(0);
  ctx.fillRect(plotX, 0, plotW, plotH);

  if (rows.length && chans) {
    const cw = plotW / 120, ch = plotH / chans;
    rows.forEach((r, x) => {
      const vals = r.channels || [];
      vals.forEach((v, y) => {
        if (y >= chans) return; // guard against a row with more channels than the latest
        const t = Math.min(1, Math.sqrt(v / 0.8));
        ctx.fillStyle = wfColor(t);
        ctx.fillRect(plotX + x * cw, y * ch, Math.ceil(cw), Math.ceil(ch));
      });
    });
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
const SPEC_VMAX = 4.0;     // color scale ceiling for mean |rfft| magnitude
const SPEC_FS_MAX = 2.0;   // Hz - Nyquist for 60 samples / 15 s window (cfg.window_seconds)

function drawSpectrogram(rows) {
  const cv = $('spectrogram'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);

  const plotX = SPEC_GUTTER;
  const plotW = cv.width - SPEC_GUTTER - SPEC_RIGHT;
  const plotH = cv.height - SPEC_TIMEBAND;

  // Plot area background (navy, i.e. t=0) so windows with no motion still read as "calm".
  ctx.fillStyle = wfColor(0);
  ctx.fillRect(plotX, 0, plotW, plotH);

  // Bin count from the latest row carrying a spectrum; rows lacking one (old data
  // written before this feature, or a skipped inference) are simply skipped below.
  const specRows = rows.filter(r => Array.isArray(r.spectrum) && r.spectrum.length);
  if (specRows.length) {
    const bins = specRows[specRows.length - 1].spectrum.length; // 30
    const cw = plotW / 120, rh = plotH / bins;
    rows.forEach((r, x) => {
      const spec = r.spectrum;
      if (!spec) return; // old row without a spectrum - graceful skip
      spec.forEach((v, i) => {
        if (i >= bins) return;
        const t = Math.min(1, Math.sqrt(v / SPEC_VMAX));
        ctx.fillStyle = wfColor(t);
        const y = plotH - (i + 1) * rh; // bin 0 (lowest freq) at the bottom
        ctx.fillRect(plotX + x * cw, y, Math.ceil(cw), Math.ceil(rh));
      });
    });
  }

  // Walking-band highlight: 0.5-2.0 Hz, i.e. the top 75% of the 0-2.0 Hz (Nyquist) axis.
  const bandTopY = 0;                                    // 2.0 Hz
  const bandBottomY = plotH * (1 - 0.5 / SPEC_FS_MAX);    // 0.5 Hz

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
    const y = plotH * (1 - f / SPEC_FS_MAX);
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

document.querySelectorAll('button[data-mode]').forEach(b =>
  b.onclick = () => j('/api/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: b.dataset.mode }) }));
$('cal').onclick = async () => {
  alert('Leave the room now. Aura will learn "empty" for 10 minutes, then ask you to walk.');
  await j('/api/calibrate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase: 'empty', minutes: 10 }) });
};
setInterval(tick, 500); tick();
