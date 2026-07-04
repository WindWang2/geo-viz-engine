// pages_maps.jsx — MapPage (well-location) + PaleoPage (paleogeographic facies)

/* deterministic scatter of wells along a basin trend */
function genWells() {
  let s = 9173;
  const r = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const pts = [];
  for (let i = 0; i < 46; i++) {
    const t = r();
    const cx = 180 + t * 520 + (r() - 0.5) * 120;
    const cy = 140 + (1 - t) * 360 + (r() - 0.5) * 150;
    pts.push({ x: cx, y: cy });
  }
  return pts;
}
const GV_WELLS = genWells();

function MapBasemap({ accentFill }) {
  return (
    <svg width="100%" height="100%" viewBox="0 0 900 720" preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0 }}>
      <rect width="900" height="720" fill="#eef2f7" />
      {/* land masses */}
      <path d="M-20 120 C140 80 230 170 360 150 C520 125 640 210 820 170 L920 150 920 740 -20 740Z" fill="#f6f4ee" />
      <path d="M-20 420 C120 380 260 430 420 410 C560 393 700 450 920 420 L920 740 -20 740Z" fill="#f1efe7" />
      {/* river */}
      <path d="M120 -10 C200 160 120 300 260 420 C360 510 300 640 420 730" fill="none" stroke="#dbe6f0" strokeWidth="9" strokeLinecap="round" />
      {/* graticule */}
      <g stroke="#dde5ee" strokeWidth="1">
        {[150, 300, 450, 600, 750].map((x) => <line key={'v' + x} x1={x} y1="0" x2={x} y2="720" />)}
        {[120, 240, 360, 480, 600].map((y) => <line key={'h' + y} x1="0" y1={y} x2="900" y2={y} />)}
      </g>
      <g fill="#aab6c4" fontSize="10" fontFamily="var(--mono)">
        {[150, 300, 450, 600, 750].map((x) => <text key={'lx' + x} x={x + 3} y="14">{(106 + x / 150 * 0.5).toFixed(1)}°E</text>)}
        {[120, 240, 360, 480, 600].map((y) => <text key={'ly' + y} x="4" y={y - 4}>{(31 - y / 120 * 0.4).toFixed(1)}°N</text>)}
      </g>
      {/* license blocks */}
      <path d="M300 200 L560 180 590 380 330 420Z" fill={accentFill} stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 5" opacity="0.9" />
      <text x="320" y="225" fill="var(--accent-ink)" fontSize="13" fontWeight="600" fontFamily="var(--font)">沧浪铺区块</text>
      <path d="M150 470 L380 450 410 600 180 630Z" fill="none" stroke="#9aa7b6" strokeWidth="1.3" strokeDasharray="5 5" />
      <text x="170" y="492" fill="#8090a0" fontSize="12" fontWeight="600" fontFamily="var(--font)">灯影探区</text>
    </svg>
  );
}

function MapPage({ dir }) {
  const selIdx = 17;
  return (
    <>
      <div className="page" style={{ flexDirection: 'row' }}>
        <aside style={{ width: 252, flex: '0 0 252px', borderRight: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '12px 12px 10px' }}>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 9, top: 8, color: 'var(--ink-3)' }}><Icon name="search" size={16} /></span>
              <input placeholder="搜索井名 / 区块…" style={{ width: '100%', padding: '7px 10px 7px 30px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface-2)', font: 'inherit', fontSize: 12.5, color: 'var(--ink)' }} />
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 9 }}>
              <span className="chip on">全部 46</span>
              <span className="chip">已解释 31</span>
              <span className="chip">含气 12</span>
            </div>
          </div>
          <div style={{ padding: '4px 12px', fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', letterSpacing: '.4px' }}>井位列表</div>
          <div className="thin-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px 8px' }}>
            {['老龙1', '老龙2', '高石1', '高石3', '磨溪8', '磨溪12', '威远2', '资阳1', '安平1', '广探2', '蜀南3', '川中4', '龙王庙7', '灯影9'].map((w, i) => (
              <div key={w} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 9px', borderRadius: 'var(--radius-sm)', background: i === 0 ? 'var(--accent-soft)' : 'transparent', color: i === 0 ? 'var(--accent-ink)' : 'var(--ink)', cursor: 'pointer', fontWeight: i === 0 ? 600 : 500 }}>
                <Icon name="pin" size={15} />
                <span style={{ flex: 1, fontSize: 12.5 }}>{w}</span>
                <span className="tag">{2400 + i * 37}m</span>
              </div>
            ))}
          </div>
        </aside>

        <div style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>
          <MapBasemap accentFill="color-mix(in oklab, var(--accent) 9%, transparent)" />
          {/* wells */}
          <svg width="100%" height="100%" viewBox="0 0 900 720" preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', inset: 0 }}>
            {GV_WELLS.map((p, i) => i === selIdx ? null : (
              <g key={i}>
                <circle cx={p.x} cy={p.y} r="4.5" fill="var(--surface)" stroke="var(--accent)" strokeWidth="1.8" />
                <circle cx={p.x} cy={p.y} r="1.6" fill="var(--accent)" />
              </g>
            ))}
            {/* selected */}
            <g>
              <circle cx={GV_WELLS[selIdx].x} cy={GV_WELLS[selIdx].y} r="13" fill="color-mix(in oklab, var(--accent) 18%, transparent)" />
              <circle cx={GV_WELLS[selIdx].x} cy={GV_WELLS[selIdx].y} r="6.5" fill="var(--accent)" stroke="#fff" strokeWidth="2.2" />
            </g>
          </svg>
          {/* selected callout */}
          <div className="card" style={{ position: 'absolute', left: `${GV_WELLS[selIdx].x / 900 * 100}%`, top: `${GV_WELLS[selIdx].y / 720 * 100}%`, transform: 'translate(14px,-50%)', padding: '9px 12px', boxShadow: 'var(--shadow-pop)' }}>
            <div style={{ fontWeight: 700, fontSize: 13 }}>老龙1 <span className="tag" style={{ marginLeft: 4 }}>含气</span></div>
            <div style={{ color: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--mono)', marginTop: 2 }}>106.32°E · 30.18°N · TD 2610m</div>
            <button className="btn primary sm" style={{ marginTop: 8 }}><Icon name="well" size={14} /> 打开井剖面</button>
          </div>
          {/* floating toolbar */}
          <div className="float-tb" style={{ top: 14, right: 14, flexDirection: 'column' }}>
            <div className="icon-btn"><Icon name="zoomIn" size={17} /></div>
            <div className="icon-btn"><Icon name="zoomOut" size={17} /></div>
            <div className="icon-btn"><Icon name="fit" size={16} /></div>
            <div className="icon-btn"><Icon name="ruler" size={16} /></div>
          </div>
          {/* layers */}
          <div className="card" style={{ position: 'absolute', top: 14, left: 14, padding: '10px 12px', minWidth: 150 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-2)', marginBottom: 7, display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="layers" size={14} /> 图层</div>
            <div className="legend">
              {[['井位点', 'var(--accent)', true], ['区块边界', '#e0b341', true], ['底图网格', '#9aa7b6', true], ['行政区', '#c0cad6', false]].map(([l, c, on]) => (
                <div className="row" key={l} style={{ opacity: on ? 1 : 0.45, fontSize: 11.5 }}><span className="sw" style={{ background: c }} />{l}</div>
              ))}
            </div>
          </div>
          {/* scale + compass */}
          <div style={{ position: 'absolute', bottom: 14, left: 14, display: 'flex', alignItems: 'flex-end', gap: 14 }}>
            <div style={{ color: 'var(--ink-2)' }}><Icon name="compass" size={30} /></div>
            <div>
              <div style={{ width: 90, height: 5, background: 'linear-gradient(90deg,var(--ink) 0 50%,var(--surface) 50% 100%)', border: '1px solid var(--ink-2)' }} />
              <div style={{ fontSize: 10, color: 'var(--ink-2)', fontFamily: 'var(--mono)', marginTop: 2 }}>0&nbsp;&nbsp;&nbsp;&nbsp;5&nbsp;&nbsp;&nbsp;10 km</div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------------- Paleogeographic facies map ---------------- */
const FACIES = [
  { n: '云质砂坪', c: '#f3e2a9', p: 'dots' },
  { n: '砂坪', c: '#f7e9b0', p: 'dots' },
  { n: '混积潮坪', c: '#cfe0f4', p: 'wave' },
  { n: '碎屑岩潮坪', c: '#bcd6ef', p: 'wave' },
  { n: '砂泥质陆棚', c: '#cdebd6', p: 'dash' },
  { n: '泥质陆棚', c: '#bce4cb', p: 'dash' },
  { n: '颗粒滩', c: '#f1d3b0', p: 'ring' },
  { n: '生屑滩', c: '#ecc9a3', p: 'ring' },
];

function PaleoPatterns() {
  return (
    <defs>
      <pattern id="pf-dots" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="1.1" fill="#b9914e" /><circle cx="9" cy="9" r="1.1" fill="#b9914e" /></pattern>
      <pattern id="pf-wave" width="16" height="10" patternUnits="userSpaceOnUse"><path d="M0 5 q4 -4 8 0 t8 0" fill="none" stroke="#6f9bd1" strokeWidth="1" /></pattern>
      <pattern id="pf-dash" width="14" height="8" patternUnits="userSpaceOnUse"><line x1="0" y1="4" x2="9" y2="4" stroke="#5fae7e" strokeWidth="1" /></pattern>
      <pattern id="pf-ring" width="13" height="13" patternUnits="userSpaceOnUse"><circle cx="6.5" cy="6.5" r="2.4" fill="none" stroke="#c98a4e" strokeWidth="1" /></pattern>
    </defs>
  );
}

function PaleoPage({ dir }) {
  const polys = [
    { d: 'M60 90 C220 60 360 120 470 90 L520 240 360 300 120 280Z', f: FACIES[2], pat: 'pf-wave' },
    { d: 'M470 90 C600 70 760 110 850 90 L850 250 520 240Z', f: FACIES[0], pat: 'pf-dots' },
    { d: 'M120 280 L360 300 520 240 540 430 300 470 90 440Z', f: FACIES[1], pat: 'pf-dots' },
    { d: 'M520 240 L850 250 850 470 540 430Z', f: FACIES[6], pat: 'pf-ring' },
    { d: 'M90 440 L300 470 540 430 560 620 250 660 70 600Z', f: FACIES[4], pat: 'pf-dash' },
    { d: 'M540 430 L850 470 850 660 560 620Z', f: FACIES[5], pat: 'pf-dash' },
  ];
  return (
    <div className="page" style={{ flexDirection: 'row' }}>
      <div style={{ position: 'relative', flex: 1, overflow: 'hidden', background: '#eef2f7' }}>
        <svg width="100%" height="100%" viewBox="0 0 900 720" preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', inset: 0 }}>
          <PaleoPatterns />
          <rect width="900" height="720" fill="#eef3f8" />
          {polys.map((p, i) => (
            <g key={i}>
              <path d={p.d} fill={p.f.c} stroke="#fff" strokeWidth="2" />
              <path d={p.d} fill={`url(#${p.pat})`} opacity="0.5" />
            </g>
          ))}
          {/* paleo-coastline */}
          <path d="M120 280 L360 300 520 240 540 430 560 620" fill="none" stroke="#7a8aa0" strokeWidth="2" strokeDasharray="2 3" />
          {/* labels */}
          <g fontFamily="var(--font)" fontWeight="600" fontSize="14" fill="#5a6878">
            <text x="250" y="195">混积潮坪</text><text x="640" y="175">云质砂坪</text>
            <text x="290" y="380">砂&nbsp;坪</text><text x="660" y="360">颗粒滩</text>
            <text x="270" y="555">砂泥质陆棚</text><text x="680" y="560">泥质陆棚</text>
          </g>
          {/* wells */}
          {[[300, 250], [560, 200], [410, 360], [690, 330], [340, 540], [620, 560], [180, 360], [760, 470]].map((p, i) => (
            <g key={i}><path d={`M${p[0]} ${p[1] - 9} L${p[0]} ${p[1]} M${p[0] - 6} ${p[1] - 6} L${p[0] + 6} ${p[1] - 6}`} stroke="#1a2433" strokeWidth="1.6" /><circle cx={p[0]} cy={p[1]} r="3" fill="#1a2433" /></g>
          ))}
        </svg>
        {/* title chrome */}
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font)', fontWeight: 700, fontSize: 17, color: 'var(--ink)' }}>沧浪铺组 沉积期 岩相古地理图</div>
          <div style={{ fontSize: 11.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>Plate Carrée · 寒武系 下寒武统</div>
        </div>
        <div className="float-tb" style={{ top: 14, right: 14, flexDirection: 'column' }}>
          <div className="icon-btn"><Icon name="zoomIn" size={17} /></div>
          <div className="icon-btn"><Icon name="zoomOut" size={17} /></div>
          <div className="icon-btn"><Icon name="fit" size={16} /></div>
        </div>
        <div style={{ position: 'absolute', bottom: 14, left: 14, color: 'var(--ink-2)' }}><Icon name="compass" size={32} /></div>
      </div>
      {/* right legend panel */}
      <aside style={{ width: 230, flex: '0 0 230px', borderLeft: '1px solid var(--border)', background: 'var(--surface)', padding: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', letterSpacing: '.4px', marginBottom: 9 }}>沉积相图例</div>
          <div className="legend">
            {FACIES.map((f) => (<div className="row" key={f.n}><span className="sw" style={{ background: f.c }} />{f.n}</div>))}
          </div>
        </div>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-3)', letterSpacing: '.4px', marginBottom: 9 }}>图层 / 标注</div>
          <div className="legend">
            {[['古海岸线', true], ['井位投影', true], ['相边界', true], ['等厚线', false]].map(([l, on]) => (
              <label key={l} className="row" style={{ cursor: 'pointer' }}><span style={{ width: 26, height: 15, borderRadius: 999, background: on ? 'var(--accent)' : 'var(--border-strong)', position: 'relative', flex: '0 0 auto' }}><span style={{ position: 'absolute', top: 2, left: on ? 13 : 2, width: 11, height: 11, borderRadius: '50%', background: '#fff', transition: '.15s' }} /></span>{l}</label>
            ))}
          </div>
        </div>
        <button className="btn" style={{ marginTop: 'auto' }}><Icon name="export" size={15} /> 导出图件</button>
      </aside>
    </div>
  );
}

Object.assign(window, { MapPage, PaleoPage });
