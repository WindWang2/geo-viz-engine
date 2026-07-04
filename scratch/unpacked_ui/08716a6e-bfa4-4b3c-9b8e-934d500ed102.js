// pages_logs.jsx — WellLogPage (comprehensive interpretation) + CrossWellPage
// helpers exported, components exported to window.

function gvCurve(seed, n, lo, hi, jag) {
  let s = seed;
  const r = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const v = [];
  let cur = (lo + hi) / 2;
  for (let i = 0; i < n; i++) {
    cur += (r() - 0.5) * (hi - lo) * jag;
    cur = Math.max(lo, Math.min(hi, cur));
    v.push(cur);
  }
  return v;
}

function curvePath(vals, lo, hi, w, h) {
  const n = vals.length;
  return vals.map((v, i) => {
    const x = ((v - lo) / (hi - lo)) * w;
    const y = (i / (n - 1)) * h;
    return (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
  }).join(' ');
}

window.gvCurve = gvCurve;
window.curvePath = curvePath;
