import React from 'react';

/**
 * LithologyPatterns - Global SVG definitions for geological symbols.
 * Patterns based on GB/T 勘探管理图件图册编制规范 附录M 岩石图式.
 * Usage: fill="url(#pattern-xxx)"
 */
export const LithologyPatterns: React.FC = () => {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        {/* 砂岩 Sandstone: 不规则圆点 */}
        <pattern id="pattern-sandstone" patternUnits="userSpaceOnUse" width="20" height="20">
          <rect width="20" height="20" fill="#fef9c3" />
          <circle cx="3" cy="3" r="1.2" fill="#92400e" />
          <circle cx="10" cy="6" r="1.0" fill="#92400e" />
          <circle cx="16" cy="2" r="0.8" fill="#92400e" />
          <circle cx="6" cy="10" r="1.1" fill="#92400e" />
          <circle cx="14" cy="11" r="1.0" fill="#92400e" />
          <circle cx="2" cy="16" r="0.9" fill="#92400e" />
          <circle cx="9" cy="14" r="1.2" fill="#92400e" />
          <circle cx="17" cy="17" r="1.0" fill="#92400e" />
          <circle cx="12" cy="18" r="0.8" fill="#92400e" />
          <circle cx="18" cy="8" r="0.9" fill="#92400e" />
        </pattern>

        {/* 粉砂岩 Siltstone: 细密小圆点 */}
        <pattern id="pattern-siltstone" patternUnits="userSpaceOnUse" width="12" height="12">
          <rect width="12" height="12" fill="#f3f4f6" />
          <circle cx="2" cy="2" r="0.5" fill="#6b7280" />
          <circle cx="7" cy="4" r="0.4" fill="#6b7280" />
          <circle cx="4" cy="7" r="0.5" fill="#6b7280" />
          <circle cx="10" cy="2" r="0.4" fill="#6b7280" />
          <circle cx="1" cy="10" r="0.5" fill="#6b7280" />
          <circle cx="6" cy="9" r="0.4" fill="#6b7280" />
          <circle cx="10" cy="7" r="0.5" fill="#6b7280" />
          <circle cx="9" cy="11" r="0.4" fill="#6b7280" />
          <circle cx="3" cy="5" r="0.3" fill="#6b7280" />
          <circle cx="8" cy="1" r="0.3" fill="#6b7280" />
        </pattern>

        {/* 泥岩 Mudstone: 短横线 */}
        <pattern id="pattern-mudstone" patternUnits="userSpaceOnUse" width="16" height="8">
          <rect width="16" height="8" fill="#d1d5db" />
          <line x1="0" y1="2" x2="6" y2="2" stroke="#4b5563" strokeWidth="0.5" />
          <line x1="9" y1="4" x2="16" y2="4" stroke="#4b5563" strokeWidth="0.5" />
          <line x1="2" y1="6" x2="8" y2="6" stroke="#4b5563" strokeWidth="0.5" />
        </pattern>

        {/* 页岩 Shale: 密集平行横线 */}
        <pattern id="pattern-shale" patternUnits="userSpaceOnUse" width="16" height="6">
          <rect width="16" height="6" fill="#9ca3af" />
          <line x1="0" y1="1.5" x2="16" y2="1.5" stroke="#374151" strokeWidth="0.6" />
          <line x1="0" y1="4.5" x2="16" y2="4.5" stroke="#374151" strokeWidth="0.6" />
        </pattern>

        {/* 灰岩 Limestone: 砖块状图案 */}
        <pattern id="pattern-limestone" patternUnits="userSpaceOnUse" width="24" height="16">
          <rect width="24" height="16" fill="#e0e7ff" />
          <line x1="0" y1="0" x2="24" y2="0" stroke="#4338ca" strokeWidth="0.6" />
          <line x1="0" y1="8" x2="24" y2="8" stroke="#4338ca" strokeWidth="0.6" />
          <line x1="8" y1="0" x2="8" y2="8" stroke="#4338ca" strokeWidth="0.4" />
          <line x1="18" y1="0" x2="18" y2="8" stroke="#4338ca" strokeWidth="0.4" />
          <line x1="4" y1="8" x2="4" y2="16" stroke="#4338ca" strokeWidth="0.4" />
          <line x1="14" y1="8" x2="14" y2="16" stroke="#4338ca" strokeWidth="0.4" />
        </pattern>

        {/* 白云岩 Dolomite: 菱形网格/斜交线 */}
        <pattern id="pattern-dolomite" patternUnits="userSpaceOnUse" width="16" height="16">
          <rect width="16" height="16" fill="#dbeafe" />
          <line x1="0" y1="0" x2="16" y2="0" stroke="#1e40af" strokeWidth="0.5" />
          <line x1="0" y1="8" x2="16" y2="8" stroke="#1e40af" strokeWidth="0.5" />
          <line x1="4" y1="0" x2="8" y2="8" stroke="#1e40af" strokeWidth="0.4" />
          <line x1="12" y1="0" x2="16" y2="8" stroke="#1e40af" strokeWidth="0.4" />
          <line x1="0" y1="0" x2="4" y2="8" stroke="#1e40af" strokeWidth="0.4" />
          <line x1="8" y1="0" x2="12" y2="8" stroke="#1e40af" strokeWidth="0.4" />
        </pattern>
      </defs>
    </svg>
  );
};
