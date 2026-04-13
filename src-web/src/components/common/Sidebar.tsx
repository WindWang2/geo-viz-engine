import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Home, Activity } from "lucide-react";

interface NavItem {
  to: string;
  icon: React.ReactNode;
  labelKey: string;
}

const navItems: NavItem[] = [
  { to: "/",         icon: <Home size={18} />,     labelKey: "nav.home" },
  { to: "/well-log", icon: <Activity size={18} />, labelKey: "nav.wellLog" },
];

export default function Sidebar() {
  const { t } = useTranslation();

  return (
    <nav className="w-48 flex-shrink-0 bg-geo-surface border-r border-geo-border flex flex-col py-2">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            `flex items-center gap-2 px-4 py-2.5 text-sm transition-colors ${
              isActive
                ? "bg-geo-accent/20 text-geo-accent border-r-2 border-geo-accent"
                : "text-geo-muted hover:text-geo-text hover:bg-white/5"
            }`
          }
        >
          {item.icon}
          <span>{t(item.labelKey)}</span>
        </NavLink>
      ))}
    </nav>
  );
}
