import { X, ChevronLeft } from 'lucide-react';
import { WellLogViewer } from '../well-log';
import type { WellLogData } from '../well-log/types';
import { useKeyboardClose } from '../../hooks/useKeyboardClose';

interface DetailPanelProps {
  wellId: string;
  wellName: string;
  wellData: WellLogData | null;
  open: boolean;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onBack: () => void;
}

export default function DetailPanel({
  wellName,
  wellData,
  open,
  loading = false,
  error = null,
  onClose,
}: DetailPanelProps) {
  useKeyboardClose(onClose, open);

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed right-0 top-0 h-full bg-white border-l border-geo-border shadow-xl z-50
                   flex flex-col w-[55vw] min-w-[380px]"
        style={{ maxWidth: '55vw' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b border-geo-border bg-geo-surface">
          <button
            onClick={onClose}
            title="返回地图"
            className="flex items-center gap-1 text-sm text-geo-accent hover:text-geo-accent/80 transition-colors"
          >
            <ChevronLeft size={18} />
            <span>返回</span>
          </button>
          <div className="flex-1 text-center font-semibold text-geo-text text-base">
            {wellName}
          </div>
          <button
            onClick={onClose}
            title="关闭"
            className="p-1 rounded hover:bg-geo-accent/10 text-geo-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Meta strip */}
        {!loading && wellData && (
          <div className="flex-shrink-0 px-4 py-1.5 text-xs text-geo-muted bg-geo-surface/50 border-b border-geo-border">
            深度 {wellData.depth_start.toFixed(1)} - {wellData.depth_end.toFixed(1)} m
            {' · '}{wellData.curves.map((c) => c.name).join(', ')}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {error && (
            <div className="p-4 m-4 bg-geo-red/10 border border-geo-red/30 rounded-lg text-geo-red text-sm">
              {error}
            </div>
          )}
          {loading && (
            <div className="flex items-center justify-center h-full text-geo-muted text-sm">
              加载中...
            </div>
          )}
          {wellData && !loading && (
            <WellLogViewer wellData={wellData} />
          )}
        </div>
      </aside>
    </>
  );
}
