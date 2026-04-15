import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Map, Table2 } from 'lucide-react';

const tabs = [
  { to: '/',         icon: <Map size={16} />,    labelKey: 'nav.map' },
  { to: '/table',    icon: <Table2 size={16} />, labelKey: 'nav.table' },
];

export default function BottomTabBar() {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-1 bg-geo-surface border border-geo-border rounded-lg p-1">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
              isActive
                ? 'bg-geo-accent text-white'
                : 'text-geo-muted hover:text-geo-text hover:bg-geo-accent/10'
            }`
          }
        >
          {tab.icon}
          <span>{t(tab.labelKey)}</span>
        </NavLink>
      ))}
    </div>
  );
}
