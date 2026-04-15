import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Home, Activity, Radio, Layers, Box, Map } from "lucide-react";

/*
  第一级目录（Sidebar纵向导航，对应各可视化模块）：
    首页           → /
    测井可视化      → /well-log
    地震剖面        → /seismic
    等值线图        → /contour
    三维地质        → /3d-viewer
    地图总览        → /map

  说明：/table (数据表) 和 /well/:id (井详情) 没有放在Sidebar，
  因为它们是特殊模式——/table 用 BottomTabBar 移动端设计，
  /well/:id 则是在 MapHomePage 内展开 DetailPanel，不属于模块级导航。
*/
const navItems = [
  { to: "/",         icon: <Home size={18} />,  labelKey: "nav.home",    end: true  },
  { to: "/well-log", icon: <Activity size={18} />, labelKey: "nav.wellLog", end: false },
  { to: "/seismic",  icon: <Radio size={18} />, labelKey: "nav.seismic",  end: false },
  { to: "/contour",  icon: <Layers size={18} />,labelKey: "nav.contour",  end: false },
  { to: "/3d-viewer",icon: <Box size={18} />,   labelKey: "nav.threeD",   end: false },
  { to: "/map",      icon: <Map size={18} />,   labelKey: "nav.map",      end: false },
];

export default function Sidebar() {
  const { t } = useTranslation();

  return (
    <nav className="w-52 flex-shrink-0 bg-geo-surface border-r border-geo-border flex flex-col py-2">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `flex items-center gap-2.5 mx-2 my-0.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
              isActive
                ? "bg-geo-accent/15 text-geo-accent font-medium"
                : "text-geo-muted hover:text-geo-text hover:bg-white/5"
            }`
          }
        >
          {item.icon}
          <span>{t(item.labelKey)}</span>
        </NavLink>
      ))}

      <div className="mt-auto px-4 pt-4 pb-2">
        <div className="border-t border-geo-border pt-3">
          <p className="text-xs text-geo-muted/60">GeoViz Engine v0.1</p>
        </div>
      </div>
    </nav>
  );
}