/***************************************************************************
 * geoviz-qgis-welltrack — well-track composite renderer (core)
 *
 * SPDX-License-Identifier: MIT
 *
 * Single render path for screen and export: hosts call render() with any
 * QPainter (widget backing store, QImage, QSvgGenerator, QPrinter). The
 * renderer paints in logical (painter) units; DPI is the device's business.
 *
 * QGIS reuse: grid symbols / label text / numeric formatting come from
 * QgsPlotAxis + QgsTextRenderer + QgsRenderContext; depth-label intervals
 * come from Qgs2DXyPlot::calculateOptimisedIntervals (public API). No QGIS
 * source is copied (docs/…/04-license-provenance.md).
 ***************************************************************************/
#ifndef GEOVIZ_QWT_WELLTRACK_RENDERER_H
#define GEOVIZ_QWT_WELLTRACK_RENDERER_H

#include "geoviz/qgis_welltrack/curve_lod.h"
#include "geoviz/qgis_welltrack/depth_domain.h"
#include "geoviz/qgis_welltrack/export.h"
#include "geoviz/qgis_welltrack/track_layout.h"
#include "geoviz/qgis_welltrack/track_model.h"

#include <qgsplot.h>
#include <qgstextformat.h>

#include <QColor>
#include <QRectF>

#include <map>

namespace geoviz::qgis_welltrack
{

struct RenderStats
{
  qsizetype rawSamplesInSlices = 0;
  qsizetype envelopePoints = 0;
  int polylines = 0;
  int subpathBreaks = 0;
  qint64 prepUsec = 0;
  qint64 paintUsec = 0;
};

struct KernelStyle
{
  QColor background = Qt::white;
  QColor separator = QColor( 0, 0, 0, 70 );
  QColor headerBackground = QColor( 245, 245, 245, 255 );
  QColor headerText = Qt::black;
  QColor border = QColor( 0, 0, 0, 140 );
  QColor rulerText = Qt::black;

  //! Shared label text format (headers, ruler, axis scale). Defaults to a
  //  QGIS text format with an 8 pt sans font set by the renderer ctor.
  QgsTextFormat labelTextFormat;

  bool drawMinorDepthGrid = true;
  bool drawValueGrid = true;

  TrackLayoutOptions layoutOptions;
};

class GEOVIZ_QWT_CORE_EXPORT WellTrackRenderer
{
  public:
    WellTrackRenderer();

    const KernelStyle &style() const { return mStyle; }
    void setStyle( const KernelStyle &style ) { mStyle = style; }

    /**
     * Renders the whole composite. Thread-safe only when instances are not
     * shared; the envelope cache makes repeated renders of an unchanged
     * model/viewport cheap (single slot per series, keyed by model
     * generation + quantized depth window + bin count).
     */
    void render( QPainter *painter, const QRectF &targetRect, const WellTrackModel &model,
                 const DepthDomain &depth, RenderStats *stats = nullptr );

    /** Last layout computed by render() (for hit testing / transforms). */
    const TrackLayoutResult &lastLayout() const { return mLastLayout; }

    /** Depth label/major/minor intervals chosen for the last render. */
    struct DepthIntervals
    {
      double label = 0.0;
      double major = 0.0;
      double minor = 0.0;
      bool valid = false;
    };
    const DepthIntervals &lastDepthIntervals() const { return mDepthIntervals; }

  private:
    struct CurveCacheEntry
    {
      quint64 modelGeneration = 0;
      int bins = 0;
      double windowQuantizedTop = 0.0;
      double windowQuantizedSpan = 0.0;
      std::vector<EnvelopeSample> envelope;
    };

    // Series ids must be unique per track; the cache key is
    // (trackId, seriesId) plus generation + quantized window.
    const std::vector<EnvelopeSample> &envelopeFor( const WellTrackModel &model, TrackId trackId,
                                                    const CurveSpec &curve, int bins,
                                                    const DepthDomain &depth,
                                                    qsizetype &rawSampleCount );

    KernelStyle mStyle;
    TrackLayoutResult mLastLayout;
    DepthIntervals mDepthIntervals;

    // Interval-optimization host: a bare Qgs2DXyPlot configured with the
    // depth window; its public calculateOptimisedIntervals() picks 1-2-5
    // label/major/minor intervals (QGIS reuse instead of a hand-rolled
    // nice-number heuristic).
    Qgs2DXyPlot mIntervalHost;
    QgsPlotRenderContext mPlotContext;

    const WellTrackModel *mLastModel = nullptr;  // cache identity guard
    std::map<std::pair<TrackId, SeriesId>, CurveCacheEntry> mEnvelopeCache;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_WELLTRACK_RENDERER_H
