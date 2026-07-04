// icons.jsx — GeoViz line-icon system (single source of truth)
// <Icon name="map" size={20} stroke={1.6} />  uses currentColor.
// All glyphs drawn on a 24×24 grid, stroke-based, geology-flavored.

const GV_ICON_PATHS = {
  /* ---- navigation (8 pages) ---- */
  map: '<path d="M9 4 3.5 6.2v13.3L9 17.3l6 2.2 5.5-2.2V4L15 6.2 9 4Z"/><path d="M9 4v13.3M15 6.2v13.3"/>',
  paleo: '<circle cx="12" cy="12" r="8.3"/><path d="M3.7 12h16.6M12 3.7c2.6 2.2 2.6 14.1 0 16.6-2.6-2.5-2.6-14.4 0-16.6Z"/><path d="M5.3 7.6c2 1.1 11.4 1.1 13.4 0M5.3 16.4c2-1.1 11.4-1.1 13.4 0"/>',
  well: '<rect x="5" y="3.5" width="14" height="17" rx="1.2"/><path d="M11.5 3.5v17"/><path d="M7 7c1.2 1.3.6 3.4 1.8 4.6 1 1 .4 3.4 1.2 5.4" fill="none"/>',
  cross: '<path d="M6 3.5v17M18 3.5v17"/><path d="M6 9c3 .5 9 4 12 1.5M6 15.5c3-.6 9 2.4 12-.4" fill="none"/>',
  seismic: '<path d="M12 3.2 3.8 7v10L12 20.8 20.2 17V7L12 3.2Z"/><path d="M12 3.2v17.6M3.8 7 12 11l8.2-4"/>',
  plots: '<rect x="3.5" y="3.5" width="17" height="17" rx="1.5"/><path d="M6.5 16c2-5 5.5-5 7.5-2.4M6.5 13c2.5-6.5 7.5-6 10 0" fill="none"/><circle cx="14" cy="13.6" r="1"/>',
  data: '<ellipse cx="12" cy="6" rx="7" ry="2.8"/><path d="M5 6v12c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8V6"/><path d="M5 12c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8"/>',
  tools: '<path d="M14.7 6.3a3.7 3.7 0 0 0-4.9 4.6l-5.4 5.4a1.6 1.6 0 0 0 2.3 2.3l5.4-5.4a3.7 3.7 0 0 0 4.6-4.9l-2.4 2.4-2-.5-.5-2 2.9-1.9Z"/>',

  /* ---- utility ---- */
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1M18.4 18.4l-2.1-2.1M7.7 7.7 5.6 5.6"/>',
  layers: '<path d="m12 3.5 8.5 4.2L12 11.9 3.5 7.7 12 3.5Z"/><path d="m3.5 12 8.5 4.2L20.5 12M3.5 16.3l8.5 4.2 8.5-4.2"/>',
  export: '<path d="M12 15V3.5m0 0L8 7.5M12 3.5 16 7.5"/><path d="M4.5 14v4c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2v-4"/>',
  download: '<path d="M12 3.5V14m0 0-4-4m4 4 4-4"/><path d="M4.5 15v3c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2v-3"/>',
  upload: '<path d="M12 14.5V4m0 0L8 8m4-4 4 4"/><path d="M4.5 15v3c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2v-3"/>',
  zoomIn: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4M11 8.5v5M8.5 11h5"/>',
  zoomOut: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4M8.5 11h5"/>',
  fit: '<path d="M4 9V5.5C4 4.7 4.7 4 5.5 4H9M15 4h3.5c.8 0 1.5.7 1.5 1.5V9M20 15v3.5c0 .8-.7 1.5-1.5 1.5H15M9 20H5.5C4.7 20 4 19.3 4 18.5V15"/>',
  ruler: '<rect x="2.7" y="8.5" width="18.6" height="7" rx="1.2" transform="rotate(-20 12 12)"/><path d="m7.5 9.2 1.6 2.7M11 7.7l1 1.8M14.6 6.2l1.6 2.7"/>',
  compass: '<circle cx="12" cy="12" r="8.3"/><path d="m15 9-1.6 4.4L9 15l1.6-4.4L15 9Z"/>',
  play: '<path d="M7.5 5.5v13l11-6.5-11-6.5Z"/>',
  undo: '<path d="M7 7 3.5 10.5 7 14"/><path d="M3.5 10.5H14a5.5 5.5 0 0 1 0 11h-3.5"/>',
  redo: '<path d="m17 7 3.5 3.5L17 14"/><path d="M20.5 10.5H10a5.5 5.5 0 0 0 0 11h3.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  filter: '<path d="M3.5 5.5h17l-6.5 7.5v5l-4 2.2v-7.2L3.5 5.5Z"/>',
  pin: '<path d="M12 21s6.5-5.6 6.5-10.5a6.5 6.5 0 0 0-13 0C5.5 15.4 12 21 12 21Z"/><circle cx="12" cy="10.5" r="2.3"/>',
  fault: '<path d="M4 7h7l2 4h7M4 13h6l2 4h8" fill="none"/>',
  grid3d: '<path d="M4 8.5 12 5l8 3.5v7L12 19l-8-3.5v-7Z"/><path d="M4 8.5 12 12l8-3.5M12 12v7"/>',
  table: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><path d="M3.5 9.5h17M3.5 14.5h17M9 9.5v10"/>',
  wave: '<path d="M3 12c2-5 4-5 6 0s4 5 6 0 4-5 6 0" fill="none"/>',
  contour: '<path d="M12 5c5 0 5 14 0 14M12 8c2.4 0 2.4 8 0 8M9 5C4 5 4 19 9 19" fill="none"/>',
  chevR: '<path d="m9.5 6 6 6-6 6"/>',
  globe: '<circle cx="12" cy="12" r="8.3"/><path d="M3.7 12h16.6M12 3.7c2.6 2.2 2.6 14.1 0 16.6-2.6-2.5-2.6-14.4 0-16.6Z"/>',
  palette: '<path d="M12 3.5a8.5 8.5 0 0 0 0 17c1.4 0 2-.9 2-1.8 0-.6-.4-1-.4-1.6 0-.8.6-1.4 1.5-1.4H17a3.5 3.5 0 0 0 3.5-3.5C20.5 7.4 16.7 3.5 12 3.5Z"/><circle cx="8" cy="10" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16" cy="10" r="1"/>',
  convert: '<path d="M4 8h11l-3-3M20 16H9l3 3"/>',
  share: '<circle cx="6" cy="12" r="2.3"/><circle cx="17" cy="6" r="2.3"/><circle cx="17" cy="18" r="2.3"/><path d="m8 11 7-4M8 13l7 4"/>',
  doc: '<path d="M6 3.5h7l5 5v12a0 0 0 0 1 0 0H6V3.5Z"/><path d="M13 3.5v5h5"/>',
  check: '<path d="m5 12 5 5 9-11"/>',
  crosshair: '<circle cx="12" cy="12" r="7.5"/><path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4"/>',
};

function Icon({ name, size = 20, stroke = 1.6, style }) {
  const d = GV_ICON_PATHS[name];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={stroke} strokeLinecap="round"
      strokeLinejoin="round" style={style}
      dangerouslySetInnerHTML={{ __html: d || '' }} />
  );
}

window.Icon = Icon;
window.GV_ICON_PATHS = GV_ICON_PATHS;
