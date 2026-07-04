// pages_data.jsx — DataPage (import + table) + ToolsPage (utility grid)

function DataPage({ dir }) {
  const rows = [
    ['老龙1', '106.32', '30.18', '2610', 'LAS · XLSX', '已解释', '12.4 MB'],
    ['高石1', '105.91', '30.44', '5180', 'LAS · SEGY', '已缓存', '48.1 MB'],
    ['磨溪8', '105.77', '30.62', '4920', 'XLSX', '已缓存', '8.7 MB'],
    ['威远2', '104.62', '29.55', '3360', 'LAS', '待解释', '6.2 MB'],
    ['资阳1', '104.98', '30.12', '4470', 'SEGY', '已缓存', '120 MB'],
    ['安平1', '106.10', '30.51', '2980', 'XLSX · LAS', '已解释', '15.0 MB'],
    ['广探2', '106.44', '30.77', '3110', 'LAS', '待解释', '5.5 MB'],
  ];
  const stCol = { '已解释': '#2ca36b', '已缓存': 'var(--accent)', '待解释': '#d98a1f' };
  return (
    <div className="page-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn primary"><Icon name="upload" size={15} /> 导入数据</button>
        <button className="btn sm"><Icon name="doc" size={14} /> Excel</button>
        <button className="btn sm"><Icon name="well" size={14} /> LAS</button>
        <button className="btn sm"><Icon name="seismic" size={14} /> SEGY</button>
        <div className="spacer" />
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 9, top: 7, color: 'var(--ink-3)' }}><Icon name="search" size={15} /></span>
          <input placeholder="筛选…" style={{ padding: '6px 10px 6px 30px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface-2)', font: 'inherit', fontSize: 12, color: 'var(--ink)', width: 160 }} />
        </div>
      </div>
      <div className="kpi-row">
        <div className="kpi"><div className="v">46</div><div className="l">注册井数</div></div>
        <div className="kpi"><div className="v">231 <small>MB</small></div><div className="l">缓存占用</div></div>
        <div className="kpi"><div className="v">3</div><div className="l">数据格式</div></div>
        <div className="kpi"><div className="v" style={{ color: '#2ca36b' }}>10 <small>ms</small></div><div className="l">Calamine 秒开</div></div>
      </div>
      <div className="card thin-scroll" style={{ flex: 1, overflow: 'auto', padding: 0 }}>
        <table className="gv">
          <thead><tr><th>井名</th><th>经度</th><th>纬度</th><th>TD (m)</th><th>数据类型</th><th>状态</th><th>缓存</th><th></th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><Icon name="pin" size={14} style={{ color: 'var(--accent)' }} />{r[0]}</span></td>
                <td className="num">{r[1]}°E</td><td className="num">{r[2]}°N</td><td className="num">{r[3]}</td>
                <td><span className="tag">{r[4]}</span></td>
                <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: stCol[r[5]] }}><span style={{ width: 7, height: 7, borderRadius: '50%', background: stCol[r[5]] }} />{r[5]}</span></td>
                <td className="num">{r[6]}</td>
                <td style={{ textAlign: 'right' }}><span className="icon-btn" style={{ display: 'inline-grid', width: 26, height: 26 }}><Icon name="chevR" size={15} /></span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ToolsPage({ dir }) {
  const tools = [
    { ic: 'convert', n: '测井 XML 转换', d: '复杂测井 XML → 标准 LaoLong Excel', tag: '常用' },
    { ic: 'ruler', n: '单位换算器', d: '深度 / 速度 / 电阻率单位互转', tag: '' },
    { ic: 'export', n: '批量矢量导出', d: '多井 SVG / PDF 长卷批处理', tag: '' },
    { ic: 'check', n: '数据完整性校验', d: 'LAS / SEGY 头段与采样一致性检查', tag: '' },
    { ic: 'layers', n: '层位插值补全', d: 'nearest / RBF 填充缺失层位网格', tag: '' },
    { ic: 'share', n: '工程打包 (.gvz)', d: '导出可移植的项目工程文件', tag: 'Beta' },
  ];
  return (
    <div className="page-pad">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>工具箱</span>
        <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>独立小工具集 · 预留接入接口</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
        {tools.map((t, i) => (
          <div key={i} className="card" style={{ padding: 14, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 38, height: 38, borderRadius: 'var(--radius-sm)', background: 'var(--accent-soft)', color: 'var(--accent-ink)', display: 'grid', placeItems: 'center', flex: '0 0 auto' }}><Icon name={t.ic} size={20} /></div>
              <div style={{ fontWeight: 600, fontSize: 13.5, flex: 1 }}>{t.n}</div>
              {t.tag && <span className="tag" style={{ background: 'var(--accent-soft)', color: 'var(--accent-ink)' }}>{t.tag}</span>}
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.5 }}>{t.d}</div>
            <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--accent-ink)', fontWeight: 600 }}>打开 <Icon name="chevR" size={14} /></div>
          </div>
        ))}
        <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, border: '1.5px dashed var(--border-strong)', background: 'var(--surface-2)', color: 'var(--ink-3)' }}>
          <Icon name="plus" size={22} /><div style={{ fontSize: 12.5, fontWeight: 500 }}>接入新工具</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { DataPage, ToolsPage });
