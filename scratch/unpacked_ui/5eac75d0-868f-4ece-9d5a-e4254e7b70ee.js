// app_a.jsx — Standalone interactive GeoViz Engine (Direction A · 蓝铜 Azurite)
// Working sidebar navigation across all 8 pages. Fills the viewport.

const A_TWEAKS = /*EDITMODE-BEGIN*/{
  "accent": "#1f66d4",
  "font": "IBM Plex Sans"
}/*EDITMODE-END*/;

function HCtxA({ title, sub }) {
  return (<div className="hdr-ctx"><div className="hdr-title">{title}</div>{sub && <div className="hdr-sub">{sub}</div>}</div>);
}
const IBA = ({ n, onClick }) => <div className="icon-btn" onClick={onClick}><Icon name={n} size={17} /></div>;

function defA(key, nav) {
  switch (key) {
    case 'map': return { Comp: MapPage, ctx: <HCtxA title="地图总览" sub="46 口井 · EPSG:4326" />, tools: <><IBA n="layers" /><IBA n="ruler" /><IBA n="settings" /></>, status: '地图就绪 · 中心 106.1°E 30.3°N · zoom 7' };
    case 'paleo': return { Comp: PaleoPage, ctx: <HCtxA title="古地理图" sub="沧浪铺组 · Plate Carrée" />, tools: <><IBA n="layers" /><IBA n="palette" /><IBA n="export" /></>, status: '古地理图 · 6 相带 · 8 井投影' };
    case 'well': return { Comp: WellLogPage, ctx: <div className="hdr-ctx"><div className="hdr-back" onClick={() => nav('map')}><Icon name="chevR" size={15} style={{ transform: 'rotate(180deg)' }} /> 返回</div><div className="hdr-divider" /><div className="hdr-title">老龙1</div><div className="hdr-sub">DEPTH 2515–2610m</div></div>, tools: <><div className="seg"><button className="on">测井图</button><button>数据</button></div><IBA n="layers" /></>, status: '老龙1 · 11 轨道 · 1:500' };
    case 'cross': return { Comp: CrossWellPage, ctx: <HCtxA title="连井对比" sub="4 wells · PCA" />, tools: <><IBA n="undo" /><IBA n="redo" /><IBA n="export" /></>, status: '连井剖面 · 16 拾取点 · DTW 就绪' };
    case 'seismic': return { Comp: SeismicPage, ctx: <HCtxA title="地震 3D" sub="synthetic.sgy" />, tools: <><IBA n="grid3d" /><IBA n="palette" /><IBA n="settings" /></>, status: '体渲染 · 512×384×600 · LRU 50' };
    case 'plots': return { Comp: PlotsPage, ctx: <HCtxA title="平面图件" sub="砂体厚度 · IDW" />, tools: <><IBA n="contour" /><IBA n="palette" /><IBA n="export" /></>, status: '等值图 · 网格 200×200 · 22 控制点' };
    case 'data': return { Comp: DataPage, ctx: <HCtxA title="数据管理" sub="46 datasets" />, tools: <><IBA n="filter" /><IBA n="upload" /></>, status: '缓存 231 MB · Calamine 引擎' };
    case 'tools': return { Comp: ToolsPage, ctx: <HCtxA title="工具箱" sub="6 工具" />, tools: <><IBA n="settings" /></>, status: '工具箱 · 6 个可用工具' };
    default: return {};
  }
}

function NavA({ page, onNav }) {
  const item = (n) => (
    <div key={n.key} onClick={() => onNav(n.key)} className={'nav-item' + (n.key === page ? ' on' : '')}>
      <span className="ni-ico"><Icon name={n.icon} size={19} /></span>{n.label}
    </div>
  );
  return (
    <nav className="side">
      <div className="side-group-label">可视化</div>
      {NAV.slice(0, 6).map(item)}
      <div className="side-group-label">工作区</div>
      {NAV.slice(6).map(item)}
      <div className="side-foot"><div className="nav-item"><span className="ni-ico"><Icon name="settings" size={19} /></span>设置</div></div>
    </nav>
  );
}

function AppA() {
  const [page, setPage] = React.useState('map');
  const [t, setTweak] = useTweaks(A_TWEAKS);
  const d = defA(page, setPage);
  const C = d.Comp;
  const style = { width: '100vw', height: '100vh', '--tw-accent-a': t.accent, '--tw-font-latin': `'${t.font}'` };
  return (
    <div className="app dir-a" style={style}>
      <header className="hdr">
        <div className="brand">
          <div className="brand-mark"><Icon name="seismic" size={16} stroke={1.8} /></div>
          <div className="brand-name">GeoViz <span className="dim">Engine</span></div>
        </div>
        <div className="hdr-divider" />
        {d.ctx}
        <div className="hdr-spacer" />
        <div className="hdr-tools">
          {d.tools}
          <div className="hdr-divider" />
          <div className="lang"><Icon name="globe" size={16} /> 中文</div>
        </div>
      </header>
      <div className="app-body">
        <NavA page={page} onNav={setPage} />
        <main className="page"><C dir="a" nav={setPage} /></main>
      </div>
      <footer className="status">
        <span className="dot" /> {d.status}
        <span className="sp" />
        <span>GeoViz Engine v0.8.0</span>
      </footer>

      <TweaksPanel>
        <TweakSection label="强调色" />
        <TweakColor label="主色" value={t.accent}
          options={['#1f66d4', '#2b6cb0', '#3a5bd0', '#15598c']}
          onChange={(v) => setTweak('accent', v)} />
        <TweakSection label="字体" />
        <TweakSelect label="西文字体" value={t.font}
          options={['IBM Plex Sans', 'Manrope', 'Sora']}
          onChange={(v) => setTweak('font', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<AppA />);
