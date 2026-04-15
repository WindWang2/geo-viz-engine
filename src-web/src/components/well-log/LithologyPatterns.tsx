import React from 'react';

/**
 * LithologyPatterns - Global SVG definitions for geological symbols.
 * These patterns can be used as 'fill="url(#pattern-id)"' in any SVG element.
 */
export const LithologyPatterns: React.FC = () => {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        {/* Sandstone: Stippled/Dots (Yellow-ish background in practice) */}
        <pattern id="pattern-sandstone" x="0" y="0" width="10" height="10" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="0.8" fill="black" />
          <circle cx="7" cy="7" r="0.8" fill="black" />
          <circle cx="4" cy="5" r="0.5" fill="black" opacity="0.5" />
        </pattern>

        {/* Shale: Close horizontal lines (Gray background) */}
        <pattern id="pattern-shale" x="0" y="0" width="20" height="4" patternUnits="userSpaceOnUse">
          <line x1="0" y1="2" x2="20" y2="2" stroke="black" strokeWidth="0.5" />
        </pattern>

        {/* Limestone: Brick pattern (Blue-ish background) */}
        <pattern id="pattern-limestone" x="0" y="0" width="30" height="15" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="30" y2="0" stroke="black" strokeWidth="1" />
          <line x1="0" y1="7.5" x2="30" y2="7.5" stroke="black" strokeWidth="1" />
          <line x1="10" y1="0" x2="10" y2="7.5" stroke="black" strokeWidth="1" />
          <line x1="25" y1="7.5" x2="25" y2="15" stroke="black" strokeWidth="1" />
        </pattern>

        {/* Dolomite: Tilted bricks (Purple-ish background) */}
        <pattern id="pattern-dolomite" x="0" y="0" width="30" height="15" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="30" y2="0" stroke="black" strokeWidth="1" />
          <line x1="0" y1="7.5" x2="30" y2="7.5" stroke="black" strokeWidth="1" />
          <line x1="5" y1="0" x2="15" y2="7.5" stroke="black" strokeWidth="1" />
          <line x1="20" y1="7.5" x2="30" y2="15" stroke="black" strokeWidth="1" />
        </pattern>

        {/* Siltstone: Dashed lines and dots */}
        <pattern id="pattern-siltstone" x="0" y="0" width="20" height="6" patternUnits="userSpaceOnUse">
          <line x1="0" y1="3" x2="12" y2="3" stroke="black" strokeWidth="0.5" strokeDasharray="2,2" />
          <circle cx="16" cy="3" r="0.6" fill="black" />
        </pattern>

        {/* Mudstone/Claystone: Thinner shale lines or solid gray */}
        <pattern id="pattern-mudstone" x="0" y="0" width="20" height="6" patternUnits="userSpaceOnUse">
          <line x1="0" y1="1.5" x2="20" y2="1.5" stroke="black" strokeWidth="0.3" opacity="0.7" />
          <line x1="0" y1="4.5" x2="20" y2="4.5" stroke="black" strokeWidth="0.3" opacity="0.7" />
        </pattern>
      </defs>
    </svg>
  );
};
