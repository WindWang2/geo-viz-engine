// pages_cross.jsx — CrossWellPage: stratigraphic correlation across wells

function CrossWellPage({ dir }) {
  const wells = ['老龙1', '高石1', '磨溪8', '威远2'];
  const colW = 132, gap = 96, top = 40, H = 560;
  const xOf = (i) => 20 + i * (colW + gap);
  const tops = [
    { y: 90, c: '#c0392b', n: '龙王庙顶' },
    { y: 210, c: '#2f80c4', n: '沧浪铺顶' },
    { y: 360, c: '#7a3fb0', n: '筇竹寺顶' },
    { y: 470, c: '#d98a1f', n: '灯影顶' },
  ];
  // per-well slight depth offsets to make ties non-flat
  const off = [0, 24, -16, 40];
  const total = xOf(3) + colW + 20;

  return (
    <div className="page-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontWeight: 600 }}>连井对比剖面</span>
        <span className="tag">4 口井 · PCA 自动排井</span>
        <div className="spacer" />
        <div className="seg"><button className="on">拾取</button><button>连接</button><button>浏览</button></div>
        <button className="btn sm"><Icon name="wave" size={14} /> DTW 自动对比</button>
        <div className="icon-btn"><Icon name="undo" size={16} /></div>
        <div className="icon-btn"><Icon name="redo" size={16} /></div>
        <button className="btn sm primary"><Icon name="export" size={14} /> 超宽 SVG</button>
      </div>

      <div className="card thin-scroll" style={{ flex: 1, overflow: 'auto', padding: 0 }}>
        <svg width={total} height={H + top + 40} style={{ display: 'block', minWidth: total }}>
          <LithoPatterns />
          {/* facies connectivity bands between wells */}
          {wells.slice(0, -1).map((_, i) => {
            const x1 = xOf(i) + colW, x2 = xOf(i + 1);
            const a1 = top + 210 + off[i], a2 = top + 210 + off[i + 1];
            const b1 = top + 360 + off[i], b2 = top + 360 + off[i + 1];
            return <path key={i} d={`M${x1} ${a1} C${(x1 + x2) / 2} ${a1} ${(x1 + x2) / 2} ${a2} ${x2} ${a2} L${x2} ${b2} C${(x1 + x2) / 2} ${b2} ${(x1 + x2) / 2} ${b1} ${x1} ${b1}Z`} fill="#cdebd6" opacity="0.5" />;
          })}
          {/* tie lines */}
          {tops.map((t, ti) => (
            <g key={ti}>
              {wells.slice(0, -1).map((_, i) => {
                const x1 = xOf(i) + colW, x2 = xOf(i + 1);
                const y1 = top + t.y + off[i], y2 = top + t.y + off[i + 1];
                return <path key={i} d={`M${x1} ${y1} C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}`} fill="none" stroke={t.c} strokeWidth="1.6" strokeDasharray="5 4" />;
              })}
            </g>
          ))}
          {/* wells */}
          {wells.map((w, i) => {
            const x = xOf(i), o = off[i];
            const gr = gvCurve(11 + i * 7, 120, 0, 150, 0.16);
            return (
              <g key={w}>
                <rect x={x} y={top + o} width={colW} height={H} fill="var(--surface)" stroke="var(--border)" />
                {/* lithology strip */}
                <rect x={x} y={top + o} width="22" height={H} fill="url(#lt-sand)" />
                <rect x={x} y={top + 150 + o} width="22" height="80" fill="url(#lt-dolo)" />
                <rect x={x} y={top + 300 + o} width="22" height="120" fill="url(#lt-shale)" />
                {/* GR curve */}
                <path d={gr.map((v, k) => { const cx = x + 30 + (v / 150) * (colW - 40); const cy = top + o + (k / (gr.length - 1)) * H; return (k ? 'L' : 'M') + cx.toFixed(1) + ' ' + cy.toFixed(1); }).join(' ')} fill="none" stroke="#2f9e57" strokeWidth="1.2" />
                {/* tops pick dots */}
                {tops.map((t, ti) => <circle key={ti} cx={x + colW / 2} cy={top + t.y + o} r="3.2" fill={t.c} stroke="#fff" strokeWidth="1.2" />)}
                {/* header */}
                <rect x={x} y={top + o - 26} width={colW} height="22" rx="4" fill="var(--accent-soft)" />
                <text x={x + colW / 2} y={top + o - 11} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--accent-ink)" fontFamily="var(--font)">{w}</text>
              </g>
            );
          })}
          {/* top labels */}
          {tops.map((t, ti) => (<text key={ti} x="8" y={top + t.y + 4} fontSize="9.5" fill={t.c} fontFamily="var(--mono)" fontWeight="600">{t.n}</text>))}
          {/* DTW ghost pick suggestion */}
          <circle cx={xOf(2) + colW / 2} cy={top + 300 + off[2]} r="5" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="2 2" />
        </svg>
      </div>
    </div>
  );
}

window.CrossWellPage = CrossWellPage;
