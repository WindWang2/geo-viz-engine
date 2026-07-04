// pages_logs.jsx — WellLogPage: comprehensive well-log interpretation chart

const WL_TOP = 2515, WL_BOT = 2610, WL_H = 1040;
const wlY = (d) => ((d - WL_TOP) / (WL_BOT - WL_TOP)) * WL_H;

const LITHO = [
  { a: 2515, b: 2528, pat: 'lt-dolo', label: '深灰色砂质白云岩' },
  { a: 2528, b: 2545, pat: 'lt-sand', label: '浅灰色砂岩' },
  { a: 2545, b: 2549, pat: 'lt-shale', label: '灰绿色页岩' },
  { a: 2549, b: 2556, pat: 'lt-silt', label: '灰黑色泥质粉砂岩' },
  { a: 2556, b: 2610, pat: 'lt-sand', label: '深灰色粉砂质泥岩' },
];
const DESC = [
  [2521, '灰色白云质细砂岩'], [2536, '浅灰色砂岩'], [2541, '深灰色泥质细砂岩'],
  [2547, '灰绿色页岩'], [2552, '灰黑色泥质粉砂岩'], [2560, '深灰色粉砂质泥岩'],
];
const FAC_MICRO = [
  { a: 2515, b: 2530, n: '云质砂坪', c: '#f3e2a9' },
  { a: 2530, b: 2545, n: '砂坪', c: '#f7e9b0' },
  { a: 2545, b: 2552, n: '泥质陆棚', c: '#bce4cb' },
  { a: 2552, b: 2610, n: '砂泥质陆棚', c: '#cdebd6' },
];
const FAC_SUB = [
  { a: 2515, b: 2528, n: '混积潮坪', c: '#cfe0f4' },
  { a: 2528, b: 2545, n: '碎屑岩潮坪', c: '#bcd6ef' },
  { a: 2545, b: 2610, n: '碎屑岩浅水陆棚', c: '#cdebd6' },
];
const FAC_MAIN = [
  { a: 2515, b: 2545, n: '潮坪相', c: '#cfe0f4' },
  { a: 2545, b: 2610, n: '陆棚相', c: '#cdebd6' },
];

function LithoPatterns() {
  return (
    <defs>
      <pattern id="lt-dolo" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="#dce8f5" /><path d="M0 14 14 0M-4 4 4 -4M10 18 18 10" stroke="#8fb0d6" strokeWidth="1" /></pattern>
      <pattern id="lt-sand" width="11" height="11" patternUnits="userSpaceOnUse"><rect width="11" height="11" fill="#fcf3d4" /><circle cx="3" cy="3" r="1" fill="#caa24f" /><circle cx="8" cy="8" r="1" fill="#caa24f" /></pattern>
      <pattern id="lt-shale" width="12" height="7" patternUnits="userSpaceOnUse"><rect width="12" height="7" fill="#d7dde2" /><line x1="0" y1="3.5" x2="12" y2="3.5" stroke="#8b97a3" strokeWidth="1" /></pattern>
      <pattern id="lt-silt" width="10" height="10" patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="#e9edf0" /><circle cx="5" cy="5" r="0.9" fill="#9aa6b2" /></pattern>
    </defs>
  );
}

function TrackHead({ w, title, sub, children }) {
  return (
    <div style={{ width: w, flex: `0 0 ${w}px`, borderRight: '1px solid var(--border)', padding: '7px 6px', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center', minHeight: 58 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{title}</div>
      {sub && <div style={{ fontSize: 9.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)', marginTop: 1 }}>{sub}</div>}
      {children}
    </div>
  );
}
function blocks(arr, w) {
  return arr.map((b, i) => (
    <div key={i} style={{ position: 'absolute', left: 0, right: 0, top: wlY(b.a), height: wlY(b.b) - wlY(b.a), background: b.c, borderBottom: '1px solid rgba(255,255,255,.9)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11.5, color: '#4a5868', writingMode: (wlY(b.b) - wlY(b.a)) < 80 ? 'horizontal-tb' : 'horizontal-tb', textAlign: 'center', padding: 2 }}>{b.n}</div>
  ));
}

function WellLogPage({ dir }) {
  const ac = gvCurve(31, 200, 40, 80, 0.16);
  const gr = gvCurve(77, 200, 0, 150, 0.14);
  const rt = gvCurve(53, 200, 0.1, 1000, 0.1);
  const tw = 120, dw = 50;
  return (
    <div className="page-pad">
      {/* toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <select style={{ font: 'inherit', fontSize: 12.5, fontWeight: 600, padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--ink)' }}><option>老龙1</option></select>
        <span className="tag">2515 – 2610 m</span>
        <span className="chip">深度</span><span className="chip">1:500</span>
        <div className="spacer" />
        <div className="seg"><button className="on">综合柱状</button><button>曲线叠合</button></div>
        <button className="btn sm"><Icon name="layers" size={14} /> 轨道</button>
        <button className="btn sm primary"><Icon name="export" size={14} /> 导出 SVG</button>
      </div>

      {/* the paper */}
      <div className="card thin-scroll" style={{ flex: 1, overflow: 'auto', padding: 0 }}>
        <div style={{ minWidth: 880 }}>
          {/* title */}
          <div style={{ textAlign: 'center', padding: '10px 0 8px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>老龙1 综合测井解释图</div>
            <div style={{ fontSize: 10.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>DEPTH 2515m – 2610m · Well ID 老龙1</div>
          </div>
          {/* track headers */}
          <div style={{ display: 'flex', borderBottom: '1.5px solid var(--border-strong)', background: 'var(--surface-2)' }}>
            <TrackHead w={108} title="地层系统" sub="系/统/组/段" />
            <TrackHead w={tw} title="AC / GR"><div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 3 }}><span style={{ fontSize: 9, color: '#3a5bd0' }}>━ AC</span><span style={{ fontSize: 9, color: '#2f9e57' }}>━ GR</span></div></TrackHead>
            <TrackHead w={dw} title="深度" sub="(m)" />
            <TrackHead w={64} title="岩性" />
            <TrackHead w={tw} title="RT / RXO"><div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 3 }}><span style={{ fontSize: 9, color: '#c0392b' }}>━ RT</span><span style={{ fontSize: 9, color: '#d98a1f' }}>┅ RXO</span></div></TrackHead>
            <TrackHead w={150} title="岩性描述" />
            <TrackHead w={70} title="微相" />
            <TrackHead w={84} title="亚相" />
            <TrackHead w={64} title="相" />
            <TrackHead w={56} title="体系域" />
            <TrackHead w={44} title="层序" />
          </div>
          {/* track bodies */}
          <div style={{ display: 'flex', position: 'relative' }}>
            {/* strat */}
            <div style={{ width: 108, flex: '0 0 108px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H, display: 'flex' }}>
              {[['寒武系', 36], ['下寒武统', 30], ['沧浪铺组', 24], ['二段·一段', 18]].map(([t, fs], i) => (
                <div key={i} style={{ flex: 1, borderRight: i < 3 ? '1px solid var(--border)' : 0, display: 'grid', placeItems: 'center', fontSize: 11.5, color: 'var(--ink-2)', writingMode: 'vertical-rl', textOrientation: 'upright', letterSpacing: 2 }}>{t}</div>
              ))}
            </div>
            {/* AC/GR */}
            <div style={{ width: tw, flex: `0 0 ${tw}px`, borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              <svg width={tw} height={WL_H} style={{ display: 'block' }}>
                <g stroke="var(--border)" strokeWidth="0.5">{[0.25, 0.5, 0.75].map((f) => <line key={f} x1={tw * f} y1="0" x2={tw * f} y2={WL_H} />)}</g>
                <path d={curvePath(ac, 40, 80, tw, WL_H)} fill="none" stroke="#3a5bd0" strokeWidth="1.2" strokeDasharray="3 2" />
                <path d={curvePath(gr, 0, 150, tw, WL_H)} fill="none" stroke="#2f9e57" strokeWidth="1.3" />
              </svg>
            </div>
            {/* depth */}
            <div style={{ width: dw, flex: `0 0 ${dw}px`, borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              {[2520, 2530, 2540, 2550, 2560, 2570, 2580, 2590, 2600].map((d) => (
                <div key={d} style={{ position: 'absolute', top: wlY(d) - 7, left: 0, right: 0, textAlign: 'center', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>{d}</div>
              ))}
            </div>
            {/* litho */}
            <div style={{ width: 64, flex: '0 0 64px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              <svg width="64" height={WL_H} style={{ display: 'block' }}>
                <LithoPatterns />
                {LITHO.map((l, i) => (<rect key={i} x="0" y={wlY(l.a)} width="64" height={wlY(l.b) - wlY(l.a)} fill={`url(#${l.pat})`} stroke="#fff" strokeWidth="1" />))}
              </svg>
            </div>
            {/* RT/RXO */}
            <div style={{ width: tw, flex: `0 0 ${tw}px`, borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              <svg width={tw} height={WL_H} style={{ display: 'block' }}>
                <g stroke="var(--border)" strokeWidth="0.5">{[0.25, 0.5, 0.75].map((f) => <line key={f} x1={tw * f} y1="0" x2={tw * f} y2={WL_H} />)}</g>
                <path d={curvePath(rt, 0.1, 1000, tw, WL_H)} fill="none" stroke="#c0392b" strokeWidth="1.3" />
                <path d={curvePath(rt.map((v) => v * 0.8), 0.1, 1000, tw, WL_H)} fill="none" stroke="#d98a1f" strokeWidth="1.1" strokeDasharray="3 2" />
              </svg>
            </div>
            {/* desc */}
            <div style={{ width: 150, flex: '0 0 150px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              {DESC.map(([d, t], i) => (<div key={i} style={{ position: 'absolute', top: wlY(d), left: 8, right: 6, fontSize: 11, color: 'var(--ink-2)' }}>{t}</div>))}
            </div>
            {/* facies micro/sub/main */}
            <div style={{ width: 70, flex: '0 0 70px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>{blocks(FAC_MICRO)}</div>
            <div style={{ width: 84, flex: '0 0 84px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>{blocks(FAC_SUB)}</div>
            <div style={{ width: 64, flex: '0 0 64px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>{blocks(FAC_MAIN)}</div>
            {/* systems tract */}
            <div style={{ width: 56, flex: '0 0 56px', borderRight: '1px solid var(--border)', position: 'relative', height: WL_H }}>
              <svg width="56" height={WL_H}>
                <polygon points={`8,${wlY(2515)} 48,${wlY(2515)} 28,${wlY(2548)}`} fill="#f6d98a" opacity="0.85" />
                <polygon points={`28,${wlY(2548)} 8,${wlY(2580)} 48,${wlY(2580)}`} fill="#bcd6ef" opacity="0.85" />
                <text x="28" y={wlY(2530)} textAnchor="middle" fontSize="11" fontWeight="700" fill="#9a7a1f">HST</text>
                <text x="28" y={wlY(2566)} textAnchor="middle" fontSize="11" fontWeight="700" fill="#3a6aa5">TST</text>
              </svg>
            </div>
            {/* sequence */}
            <div style={{ width: 44, flex: '0 0 44px', position: 'relative', height: WL_H }}>
              <div style={{ position: 'absolute', top: wlY(2515), height: wlY(2580) - wlY(2515), left: 0, right: 0, display: 'grid', placeItems: 'center', fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 12, color: 'var(--ink-2)', writingMode: 'vertical-rl' }}>SQ2</div>
              <div style={{ position: 'absolute', top: wlY(2580), bottom: 0, left: 0, right: 0, display: 'grid', placeItems: 'center', fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 12, color: 'var(--ink-2)', writingMode: 'vertical-rl', borderTop: '1px solid var(--border)' }}>SQ1</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.WellLogPage = WellLogPage;
window.LithoPatterns = LithoPatterns;
