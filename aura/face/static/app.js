const $ = id => document.getElementById(id);
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
    `<li>${new Date(a.ts * 1000).toLocaleTimeString()} — ${a.type}</li>`).join('');
}

function drawWaterfall(rows) {
  const cv = $('waterfall'), ctx = cv.getContext('2d');
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);
  if (!rows.length) return;
  const chans = rows[0].channels.length, cw = cv.width / 120, ch = cv.height / chans;
  rows.forEach((r, x) => r.channels.forEach((v, y) => {
    const t = Math.min(1, v / 1.5);
    ctx.fillStyle = `rgb(${Math.round(20 + 235 * t)},${Math.round(30 + 80 * t)},${Math.round(80 + 100 * (1 - t))})`;
    ctx.fillRect(x * cw, y * ch, Math.ceil(cw), Math.ceil(ch));
  }));
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
