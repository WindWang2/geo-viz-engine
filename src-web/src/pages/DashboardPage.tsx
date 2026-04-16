'use client';

import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Activity, Radio, Layers, Box, Map } from 'lucide-react';

const modules = [
  {
    to: '/well-log',
    icon: <Activity size={28} />,
    labelKey: 'page.dashboard.modules.wellLog.name',
    descKey: 'page.dashboard.modules.wellLog.desc',
    color: 'bg-blue-50 text-blue-600',
    borderColor: 'hover:border-blue-300',
  },
  {
    to: '/seismic',
    icon: <Radio size={28} />,
    labelKey: 'page.dashboard.modules.seismic.name',
    descKey: 'page.dashboard.modules.seismic.desc',
    color: 'bg-orange-50 text-orange-600',
    borderColor: 'hover:border-orange-300',
  },
  {
    to: '/contour',
    icon: <Layers size={28} />,
    labelKey: 'page.dashboard.modules.contour.name',
    descKey: 'page.dashboard.modules.contour.desc',
    color: 'bg-green-50 text-green-600',
    borderColor: 'hover:border-green-300',
  },
  {
    to: '/3d-viewer',
    icon: <Box size={28} />,
    labelKey: 'page.dashboard.modules.threeD.name',
    descKey: 'page.dashboard.modules.threeD.desc',
    color: 'bg-purple-50 text-purple-600',
    borderColor: 'hover:border-purple-300',
  },
];

const quickLinks = [
  { to: '/map', labelKey: 'page.dashboard.quick.map', icon: <Map size={18} /> },
];

export default function DashboardPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Hero */}
      <div className="flex-shrink-0 bg-gradient-to-br from-geo-accent/10 to-transparent border-b border-geo-border px-8 py-10">
        <h1 className="text-2xl font-bold text-geo-text mb-2">
          {t('page.dashboard.welcome')}
        </h1>
        <p className="text-geo-muted text-sm">
          {t('page.dashboard.subtitle')}
        </p>
      </div>

      {/* Module Grid */}
      <div className="flex-1 px-8 py-6">
        <h2 className="text-base font-semibold text-geo-text mb-4 uppercase tracking-wide text-xs">
          {t('page.dashboard.sections.modules')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {modules.map((mod) => (
            <Link
              key={mod.to}
              to={mod.to}
              className={`group flex flex-col gap-3 p-5 rounded-xl border border-geo-border bg-white transition-all duration-200 ${mod.borderColor} hover:shadow-md hover:-translate-y-0.5`}
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${mod.color.split(' ')[0]} ${mod.color.split(' ')[1]}`}>
                {mod.icon}
              </div>
              <div>
                <p className="font-semibold text-black text-sm group-hover:text-geo-accent transition-colors">
                  {t(mod.labelKey)}
                </p>
                <p className="text-xs text-gray-600 mt-1 leading-relaxed">
                  {t(mod.descKey)}
                </p>
              </div>
            </Link>
          ))}
        </div>

        {/* Quick Links */}
        <h2 className="text-base font-semibold text-geo-text mb-4 mt-8 uppercase tracking-wide text-xs">
          {t('page.dashboard.sections.quick')}
        </h2>
        <div className="flex flex-wrap gap-3">
          {quickLinks.map((ql) => (
            <Link
              key={ql.to}
              to={ql.to}
              className="flex items-center gap-2 px-4 py-2 text-sm text-geo-muted border border-geo-border rounded-lg hover:text-geo-accent hover:border-geo-accent transition-all"
            >
              {ql.icon}
              <span>{t(ql.labelKey)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}