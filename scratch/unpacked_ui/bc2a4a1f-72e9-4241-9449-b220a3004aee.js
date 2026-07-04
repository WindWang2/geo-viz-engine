// shell.jsx — App chrome: header, sidebar (A labeled / B rail), status bar.
// Exports: NAV, AppShell, HBack, HSeg.

const NAV = [
  { key: 'map',     icon: 'map',     label: '地图总览', en: 'Map',        rail: '地图' },
  { key: 'paleo',   icon: 'paleo',   label: '古地理图', en: 'Paleo',      rail: '古地理' },
  { key: 'well',    icon: 'well',    label: '井剖面',   en: 'Well Log',   rail: '井剖面' },
  { key: 'cross',   icon: 'cross',   label: '连井对比', en: 'Cross-Well', rail: '连井' },
  { key: 'seismic', icon: 'seismic', label: '地震 3D',  en: 'Seismic',    rail: '地震' },
  { key: 'plots',   icon: 'plots',   label: '平面图件', en: 'Plots',      rail: '图件' },
  { key: 'data',    icon: 'data',    label: '数据管理', en: 'Data',       rail: '数据' },
  { key: 'tools',   icon: 'tools',   label: '工具箱',   en: 'Tools',      rail: '工具' },
];

function HSeg({ items, value }) {
  return (
    <div className="seg">
      {items.map((it) => (
        <button key={it} className={it === value ? 'on' : ''}>{it}</button>
      ))}
    </div>
  );
}

function HBack({ title, sub }) {
  return (
    <div className="hdr-ctx">
      <div className="hdr-back"><Icon name="chevR" size={15} style={{ transform: 'rotate(180deg)' }} /> 返回</div>
      <div className="hdr-divider" />
      <div className="hdr-title">{title}</div>
      {sub && <div className="hdr-sub">{sub}</div>}
    </div>
  );
}

function SidebarA({ page }) {
  return (
    <nav className="side">
      <div className="side-group-label">可视化</div>
      {NAV.slice(0, 6).map((n) => (
        <div key={n.key} className={'nav-item' + (n.key === page ? ' on' : '')}>
          <span className="ni-ico"><Icon name={n.icon} size={19} /></span>{n.label}
        </div>
      ))}
      <div className="side-group-label">工作区</div>
      {NAV.slice(6).map((n) => (
        <div key={n.key} className={'nav-item' + (n.key === page ? ' on' : '')}>
          <span className="ni-ico"><Icon name={n.icon} size={19} /></span>{n.label}
        </div>
      ))}
      <div className="side-foot">
        <div className="nav-item"><span className="ni-ico"><Icon name="settings" size={19} /></span>设置</div>
      </div>
    </nav>
  );
}

function SidebarB({ page }) {
  return (
    <nav className="rail">
      {NAV.slice(0, 6).map((n) => (
        <div key={n.key} className={'rail-item' + (n.key === page ? ' on' : '')}>
          <Icon name={n.icon} size={21} /><span className="rail-lbl">{n.rail}</span>
        </div>
      ))}
      <div className="rail-sep" />
      {NAV.slice(6).map((n) => (
        <div key={n.key} className={'rail-item' + (n.key === page ? ' on' : '')}>
          <Icon name={n.icon} size={21} /><span className="rail-lbl">{n.rail}</span>
        </div>
      ))}
      <div className="rail-foot">
        <div className="rail-item"><Icon name="settings" size={21} /></div>
      </div>
    </nav>
  );
}

function AppShell({ dir, page, ctx, tools, status, children }) {
  return (
    <div className={'app dir-' + dir}>
      <header className="hdr">
        <div className="brand">
          <div className="brand-mark"><Icon name="seismic" size={16} stroke={1.8} /></div>
          <div className="brand-name">GeoViz <span className="dim">Engine</span></div>
        </div>
        <div className="hdr-divider" />
        {ctx}
        <div className="hdr-spacer" />
        <div className="hdr-tools">
          {tools}
          <div className="hdr-divider" />
          <div className="lang"><Icon name="globe" size={16} /> 中文</div>
        </div>
      </header>
      <div className="app-body">
        {dir === 'a' ? <SidebarA page={page} /> : <SidebarB page={page} />}
        <main className="page">{children}</main>
      </div>
      <footer className="status">
        <span className="dot" /> {status || '就绪'}
        <span className="sp" />
        <span>GeoViz Engine v0.8.0</span>
      </footer>
    </div>
  );
}

Object.assign(window, { NAV, HSeg, HBack, SidebarA, SidebarB, AppShell });
