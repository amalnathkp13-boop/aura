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

document.querySelectorAll('button[data-mode]').forEach(b =>
  b.onclick = () => j('/api/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: b.dataset.mode }) }));
$('cal').onclick = async () => {
  alert('Leave the room now. Aura will learn "empty" for 10 minutes, then ask you to walk.');
  await j('/api/calibrate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase: 'empty', minutes: 10 }) });
};
setInterval(tick, 500); tick();
