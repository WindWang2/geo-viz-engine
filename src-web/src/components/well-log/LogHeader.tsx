import React from 'react';

/**
 * LogHeader - Multi-level nested header for the well log dashboard.
 * 1:1 replica of demo.jpg layout using CSS Grid (17 columns).
 */
export const LogHeader: React.FC = () => {
  return (
    <div className="bg-white sticky top-0 z-20 border-t border-black select-none">
      {/* Row 1: Primary Categories */}
      <div className="log-grid h-[60px]">
        <div className="header-cell col-span-4">地层系统</div>
        <div className="header-cell relative py-1">
          <div className="flex flex-col h-full justify-between w-full px-1">
            <div className="flex justify-between items-center text-[9px] text-red-600">
              <span>70</span>
              <div className="flex flex-col items-center">
                <div className="w-8 border-t border-red-600 border-dashed"></div>
                <span className="font-bold">AC</span>
              </div>
              <span>40</span>
            </div>
            <div className="flex justify-between items-center text-[9px] text-blue-600 border-t border-gray-400 mt-0.5 pt-0.5">
              <span>0</span>
              <div className="flex flex-col items-center">
                <div className="w-8 border-t border-blue-600"></div>
                <span className="font-bold">GR</span>
              </div>
              <span>200</span>
            </div>
          </div>
        </div>
        <div className="header-cell">深<br/>度</div>
        <div className="header-cell">取<br/>心<br/>段</div>
        <div className="header-cell">岩性</div>
        <div className="header-cell">典型照片</div>
        <div className="header-cell relative py-1">
          <div className="flex flex-col h-full justify-between w-full px-1">
            <div className="flex justify-between items-center text-[9px] text-green-700">
              <span>1</span>
              <div className="flex flex-col items-center">
                <div className="w-8 border-t border-green-700"></div>
                <span className="font-bold">RT</span>
              </div>
              <span>20000</span>
            </div>
            <div className="flex justify-between items-center text-[9px] text-orange-500 border-t border-gray-400 mt-0.5 pt-0.5">
              <span>1</span>
              <div className="flex flex-col items-center">
                <div className="w-8 border-t border-orange-500 border-dashed"></div>
                <span className="font-bold">RXO</span>
              </div>
              <span>20000</span>
            </div>
          </div>
        </div>
        <div className="header-cell">岩性描述</div>
        <div className="header-cell col-span-3">沉积相</div>
        <div className="header-cell col-span-3">三级层序</div>
      </div>

      {/* Row 2: Sub-categories */}
      <div className="log-grid h-[40px] text-[10px]">
        <div className="header-cell">系</div>
        <div className="header-cell">统</div>
        <div className="header-cell">组</div>
        <div className="header-cell">段</div>
        <div className="header-cell"></div>
        <div className="header-cell">(m)</div>
        <div className="header-cell"></div>
        <div className="header-cell"></div>
        <div className="header-cell"></div>
        <div className="header-cell"></div>
        <div className="header-cell">微相</div>
        <div className="header-cell">亚相</div>
        <div className="header-cell">相</div>
        <div className="header-cell">层序<br/>结构</div>
        <div className="header-cell">体系<br/>域</div>
        <div className="header-cell">层序</div>
      </div>
    </div>
  );
};
