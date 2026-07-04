// pages_seismic.jsx — SeismicPage (3D volume + 2D profile + well-tie) and PlotsPage (contour)

function seisCol(t) { // t in -1..1  -> blue..white..red
  if (t >= 0) { const a = t; return `rgb(${Math.round(255)},${Math.round(255 - a * 200)},${Math.round(255 - a * 210)})`; }
  const a = -t; return `rgb(${Math.round(255 - a * 210)},${Math.round(255 - a * 170)},${Math.round(255)})`;
}
function VDBands({ w, h, seed, nb = 26 }) {
  const bands = [];
  for (let k = 0; k < nb; k++) {
    const y0 = k / nb * h, y1 = (k + 1) / nb * h, ph = k * 0.9 + seed;
    const N = 16;
    let d = '';
    for (let j = 0; j <= N; j++) { const x = j / N * w; const y = y0 + Math.sin(x * 0.025 + ph) * 4; d += (j ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1); }
    for (let j = N; j >= 0; j--) { const x = j / N * w; const y = y1 + Math.sin(x * 0.025 + ph + 0.6) * 4; d += 'L' + x.toFixed(1) + ' ' + y.toFixed(1); }
    const amp = Math.sin(k * 1.25 + seed * 0.7);
    bands.push(<path key={k} d={d + 'Z'} fill={seisCol(amp)} />);
  }
  return <g>{bands}</g>;
}

function SeismicPage({ dir }) {
  // oblique cube
  const fx0 = 70, fx1 = 380, fy0 = 70, fy1 = 330, dx = 120, dy = -64;
  return (
    <div className="page-pad" style={{ flexDirection: 'row' }}>
      {/* main column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card" style={{ flex: 1.5, position: 'relative', overflow: 'hidden', background: '#10151c' }}>
          <div style={{ position: 'absolute', top: 10, left: 12, color: '#aeb8c4', fontSize: 11.5, fontWeight: 600, zIndex: 2 }}>3D 体渲染 · GLVolumeItem</div>
          <div className="float-tb" style={{ top: 8, right: 8 }}>
            <div className="icon-btn" style={{ color: '#cdd6e0' }}><Icon name="grid3d" size={16} /></div>
            <div className="icon-btn" style={{ color: '#cdd6e0' }}><Icon name="fit" size={15} /></div>
            <div className="icon-btn" style={{ color: '#cdd6e0' }}><Icon name="crosshair" size={15} /></div>
          </div>
          <svg width="100%" height="100%" viewBox="0 0 520 380" preserveAspectRatio="xMidYMid meet">
            <clipPath id="frontclip"><rect x={fx0} y={fy0} width={fx1 - fx0} height={fy1 - fy0} /></clipPath>
            {/* top face */}
            <polygon points={`${fx0},${fy0} ${fx1},${fy0} ${fx1 + dx},${fy0 + dy} ${fx0 + dx},${fy0 + dy}`} fill="#243042" stroke="#3a4961" />
            {/* right face */}
            <polygon points={`${fx1},${fy0} ${fx1},${fy1} ${fx1 + dx},${fy1 + dy} ${fx1 + dx},${fy0 + dy}`} fill="#1b2535" stroke="#3a4961" />
            {/* front face with seismic */}
            <g clipPath="url(#frontclip)"><g transform={`translate(${fx0},${fy0})`}><VDBands w={fx1 - fx0} h={fy1 - fy0} seed={3} /></g></g>
            <rect x={fx0} y={fy0} width={fx1 - fx0} height={fy1 - fy0} fill="none" stroke="#4a5a74" />
            {/* horizon surface on top */}
            <path d={`M${fx0 + 20} ${fy0 + 12} q60 -18 120 -2 t140 4 l${dx} ${dy} q-70 -10 -140 -4 t-120 2Z`} fill="#e0a23c" opacity="0.55" stroke="#e0a23c" />
            {/* inline slice highlight */}
            <line x1={fx0 + 180} y1={fy0} x2={fx0 + 180 + dx} y2={fy0 + dy} stroke="var(--accent)" strokeWidth="2" />
            <line x1={fx0 + 180} y1={fy0} x2={fx0 + 180} y2={fy1} stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3" />
            <text x={fx0 + 186} y={fy0 + dy + 14} fill="var(--accent)" fontSize="10" fontFamily="var(--mono)">inline 420</text>
            {/* well path */}
            <line x1={fx0 + 250} y1={fy0 - 18} x2={fx0 + 250} y2={fy1} stroke="#4ad6a0" strokeWidth="1.6" />
            <circle cx={fx0 + 250} cy={fy0 - 18} r="3" fill="#4ad6a0" />
            <text x={fx0 + 256} y={fy0 - 18} fill="#4ad6a0" fontSize="10" fontFamily="var(--mono)">老龙1</text>
          </svg>
        </div>
        {/* 2D profile */}
        <div className="card" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <div className="card-h" style={{ padding: '7px 12px' }}><h3 style={{ fontSize: 12 }}>2D 剖面 · inline 420</h3><span className="tag">VD</span><div className="spacer" /><div className="seg"><button className="on">VD</button><button>Wiggle</button></div></div>
          <div style={{ position: 'relative', height: 'calc(100% - 36px)' }}>
            <svg width="100%" height="100%" viewBox="0 0 760 200" preserveAspectRatio="none">
              <VDBands w={760} h={200} seed={7} nb={22} />
              {/* synthetic wiggle overlay at well */}
              <g transform="translate(360,0)">
                <line x1="0" y1="0" x2="0" y2="200" stroke="#1a2433" strokeWidth="0.6" opacity="0.5" />
                <path d={Array.from({ length: 60 }, (_, i) => { const y = i / 59 * 200; const x = Math.sin(i * 0.6) * 14 * (0.5 + 0.5 * Math.sin(i * 0.12)); return (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1); }).join(' ')} fill="none" stroke="#111" strokeWidth="1.1" />
              </g>
            </svg>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 30, background: 'linear-gradient(90deg, var(--surface), transparent)', pointerEvents: 'none' }} />
            <div style={{ position: 'absolute', left: 6, top: 6, fontSize: 9.5, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>TWT (ms)</div>
          </div>
        </div>
      </div>
      {/* control sidebar */}
      <aside style={{ width: 226, flex: '0 0 226px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', marginBottom: 9 }}>切片控制</div>
          {[['Inline', 420, 280, 560], ['Crossline', 180, 60, 320], ['Time', 1240, 800, 1800]].map(([l, v, lo, hi]) => (
            <div key={l} style={{ marginBottom: 11 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 4 }}><span style={{ color: 'var(--ink-2)' }}>{l}</span><span className="tag">{v}</span></div>
              <div style={{ height: 4, background: 'var(--surface-3)', borderRadius: 3, position: 'relative' }}><div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(v - lo) / (hi - lo) * 100}%`, background: 'var(--accent)', borderRadius: 3 }} /><div style={{ position: 'absolute', left: `${(v - lo) / (hi - lo) * 100}%`, top: -4, width: 12, height: 12, marginLeft: -6, borderRadius: '50%', background: 'var(--surface)', border: '2px solid var(--accent)' }} /></div>
            </div>
          ))}
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', margin: '4px 0 7px' }}>色标 Colormap</div>
          <div style={{ height: 14, borderRadius: 4, background: 'linear-gradient(90deg,#3358a0,#88a8d8,#fff,#e8a0a0,#c0392b)', border: '1px solid var(--border)' }} />
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}><span className="chip on">seismic</span><span className="chip">gray</span><span className="chip">jet</span></div>
        </div>
        <div className="card" style={{ padding: 12, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, marginBottom: 10 }}><Icon name="wave" size={15} /> 井震标定</div>
          {[['子波', 'Ricker'], ['主频', '30 Hz'], ['相关系数', '0.87']].map(([l, v]) => (
            <div key={l} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '5px 0', borderBottom: '1px solid var(--border)' }}><span style={{ color: 'var(--ink-2)' }}>{l}</span><span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{v}</span></div>
          ))}
          <button className="btn primary sm" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}><Icon name="crosshair" size={14} /> Auto-Tie 标定</button>
          <button className="btn sm" style={{ width: '100%', justifyContent: 'center', marginTop: 7 }}><Icon name="download" size={14} /> 导出 T-D 表</button>
        </div>
      </aside>
    </div>
  );
}

/* ---------------- Plots / contour ---------------- */
function PlotsPage({ dir }) {
  // contour control points
  let s = 4412; const r = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const pts = Array.from({ length: 22 }, () => ({ x: 60 + r() * 600, y: 50 + r() * 420, v: (r() * 40 + 10).toFixed(1) }));
  const bands = ['#2c7bb6', '#5ba7cf', '#a6d8e8', '#e6f3d8', '#fee59a', '#fdae61', '#e85d3d'];
  return (
    <div className="page-pad" style={{ flexDirection: 'row' }}>
      <div className="card" style={{ flex: 1, position: 'relative', overflow: 'hidden', minWidth: 0 }}>
        <div className="card-h"><h3>沧浪铺组 砂体厚度等值图</h3><span className="tag">IDW · 网格 200×200</span><div className="spacer" /><div className="icon-btn"><Icon name="fit" size={15} /></div></div>
        <svg width="100%" height="calc(100% - 46px)" viewBox="0 0 720 520" preserveAspectRatio="xMidYMid meet">
          {/* filled contour blobs */}
          <g>
            {bands.map((c, i) => {
              const k = bands.length - i; const rx = 70 + k * 34, ry = 50 + k * 24;
              return <ellipse key={i} cx="360" cy="250" rx={rx} ry={ry} fill={c} transform="rotate(-18 360 250)" />;
            })}
          </g>
          {/* contour lines */}
          <g fill="none" stroke="rgba(40,50,60,.35)" strokeWidth="0.8">
            {bands.map((_, i) => { const k = bands.length - i; return <ellipse key={i} cx="360" cy="250" rx={70 + k * 34} ry={50 + k * 24} transform="rotate(-18 360 250)" />; })}
          </g>
          {/* control points */}
          {pts.map((p, i) => (<g key={i}><circle cx={p.x} cy={p.y} r="2.6" fill="#1a2433" /><text x={p.x + 4} y={p.y - 3} fontSize="9" fontFamily="var(--mono)" fill="#1a2433">{p.v}</text></g>))}
          {/* axes */}
          <line x1="40" y1="490" x2="700" y2="490" stroke="var(--border-strong)" /><line x1="40" y1="20" x2="40" y2="490" stroke="var(--border-strong)" />
          <g fill="var(--ink-3)" fontSize="9" fontFamily="var(--mono)">{[0, 1, 2, 3, 4, 5].map((i) => <text key={i} x={40 + i * 130} y="505">{(106 + i * 0.1).toFixed(1)}</text>)}</g>
        </svg>
      </div>
      <aside style={{ width: 200, flex: '0 0 200px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', marginBottom: 9 }}>插值方法</div>
          <div className="seg" style={{ width: '100%' }}><button className="on" style={{ flex: 1 }}>IDW</button><button style={{ flex: 1 }}>RBF</button><button style={{ flex: 1 }}>Kriging</button></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, margin: '12px 0 4px' }}><span style={{ color: 'var(--ink-2)' }}>幂指数</span><span className="tag">2.0</span></div>
          <div style={{ height: 4, background: 'var(--surface-3)', borderRadius: 3, position: 'relative' }}><div style={{ position: 'absolute', inset: '0 50% 0 0', background: 'var(--accent)', borderRadius: 3 }} /></div>
        </div>
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', marginBottom: 9 }}>色标 (m)</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ width: 16, height: 150, borderRadius: 4, background: `linear-gradient(${bands.slice().reverse().join(',')})`, border: '1px solid var(--border)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}><span>50</span><span>38</span><span>26</span><span>14</span><span>2</span></div>
          </div>
        </div>
        <button className="btn"><Icon name="export" size={15} /> 导出 PDF</button>
      </aside>
    </div>
  );
}

Object.assign(window, { SeismicPage, PlotsPage });
