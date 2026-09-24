/***************************************************************************
 * geoviz-qgis-welltrack — well-track composite renderer implementation
 *
 * SPDX-License-Identifier: MIT
 *
 * QGIS public API reuse in this file: QgsRenderContext::fromQPainter,
 * Qgs2DXyPlot::calculateOptimisedIntervals (interval choice), QgsPlotAxis
 * grid symbols via QgsLineSymbol::renderPolyline, QgsTextRenderer::drawText
 * with QgsTextFormat, QgsNumericFormat::formatDouble. Curve polylines are
 * drawn with QPainter pens through the same render context (documented
 * decision — see docs 03-reuse-matrix.md).
 ***************************************************************************/
#include "welltrack_renderer.h"

#include <qgslinesymbol.h>
#include <qgsnumericformat.h>
#include <qgsrendercontext.h>
#include <qgstextrenderer.h>

#include <QFont>
#include <QPainter>
#include <QPolygonF>

#include <QElapsedTimer>
#include <algorithm>
#include <cmath>
#include <limits>

namespace geoviz::qgis_welltrack
{

namespace
{

QString formatAxisValue( const QgsPlotAxis *axis, double value )
{
  if ( axis && axis->numericFormat() )
    return axis->numericFormat()->formatDouble( value, QgsNumericFormatContext() );
  return QString::number( value, 'g', 6 );
}

struct PolylineRun
{
  QPolygonF points;
};

// Envelope → screen-space runs, split at breakAfter flags.
void buildRuns( const std::vector<EnvelopeSample> &envelope, const TrackAxisSpec &axis,
                const DepthDomain &depth, const QRectF &contentRect, std::vector<PolylineRun> &runs )
{
  runs.clear();
  PolylineRun current;
  for ( const EnvelopeSample &s : envelope )
  {
    const double x = axis.xForValue( s.value, contentRect );
    const double y = depth.yForDepth( s.depth, contentRect );
    if ( !std::isfinite( x ) || !std::isfinite( y ) )
      continue;
    current.points.push_back( QPointF( x, y ) );
    if ( s.breakAfter && current.points.size() >= 1 )
    {
      if ( current.points.size() >= 1 )
        runs.push_back( current );
      current.points.clear();
    }
  }
  if ( !current.points.isEmpty() )
    runs.push_back( current );
}

void drawMarkerShape( QPainter *painter, MarkerShape shape, const QPointF &center, double size,
                      const QColor &color )
{
  QRectF rect( center.x() - size / 2, center.y() - size / 2, size, size );
  painter->setPen( Qt::NoPen );
  painter->setBrush( color );
  switch ( shape )
  {
    case MarkerShape::Circle:
      painter->drawEllipse( rect );
      break;
    case MarkerShape::Square:
      painter->drawRect( rect );
      break;
    case MarkerShape::Diamond:
    {
      QPolygonF diamond;
      diamond << QPointF( center.x(), rect.top() ) << QPointF( rect.right(), center.y() )
              << QPointF( center.x(), rect.bottom() ) << QPointF( rect.left(), center.y() );
      painter->drawPolygon( diamond );
      break;
    }
    case MarkerShape::Cross:
    {
      painter->setBrush( Qt::NoBrush );
      painter->setPen( QPen( color, 1.0 ) );
      painter->drawLine( QPointF( rect.left(), rect.top() ), QPointF( rect.right(), rect.bottom() ) );
      painter->drawLine( QPointF( rect.left(), rect.bottom() ), QPointF( rect.right(), rect.top() ) );
      break;
    }
    case MarkerShape::None:
      break;
  }
}

QColor fillColorWithOpacity( QColor base, qreal opacity )
{
  if ( !base.isValid() )
    base = Qt::gray;
  const qreal alpha = base.alphaF() * opacity;
  base.setAlphaF( alpha );
  return base;
}

} // namespace

WellTrackRenderer::WellTrackRenderer()
{
  QFont font( QStringLiteral( "Sans Serif" ) );
  font.setPointSize( 8 );
  mStyle.labelTextFormat.setFont( font );
  mStyle.labelTextFormat.setColor( QColor( 30, 30, 30 ) );
}

const std::vector<EnvelopeSample> &WellTrackRenderer::envelopeFor( const WellTrackModel &model,
                                                                   const CurveSpec &curve, int bins,
                                                                   const DepthDomain &depth,
                                                                   qsizetype &rawSampleCount )
{
  const quint64 generation = model.generation();
  const double span = depth.span();
  const double quantum = ( bins > 0 && span > 0 ) ? span / bins : span;

  // Quantized window key: panning inside one bin re-renders from the same
  // envelope (reference behavior from geoviz_well_log's path cache).
  double quantTop = depth.minDepth();
  double quantSpan = span;
  if ( quantum > 0 )
  {
    quantTop = std::round( depth.minDepth() / quantum ) * quantum;
    quantSpan = std::round( span / quantum ) * quantum;
  }

  CurveCacheEntry &entry = mEnvelopeCache[ curve.id ];
  const VisibleSlice slice = visibleSlice( curve.data, depth.minDepth(), depth.maxDepth() );
  rawSampleCount = slice.size();
  if ( entry.modelGeneration != generation || entry.bins != bins ||
       entry.windowQuantizedTop != quantTop || entry.windowQuantizedSpan != quantSpan )
  {
    buildEnvelope( curve.data, slice, bins, entry.envelope );

    entry.modelGeneration = generation;
    entry.bins = bins;
    entry.windowQuantizedTop = quantTop;
    entry.windowQuantizedSpan = quantSpan;
  }
  return entry.envelope;
}

void WellTrackRenderer::render( QPainter *painter, const QRectF &targetRect,
                                const WellTrackModel &model, const DepthDomain &depth,
                                RenderStats *stats )
{
  if ( !painter )
    return;

  QElapsedTimer prepTimer;
  prepTimer.start();

  if ( stats )
    *stats = RenderStats();

  painter->save();
  painter->fillRect( targetRect, mStyle.background );

  mLastLayout = computeTrackLayout( model, targetRect, mStyle.layoutOptions );
  const TrackLayoutResult &layout = mLastLayout;

  QgsRenderContext rc = QgsRenderContext::fromQPainter( painter );
  rc.setFlag( Qgis::RenderContextFlag::Antialiasing, true );

  // Drop cache entries from older generations / removed series.
  if ( !mEnvelopeCache.empty() )
  {
    for ( auto it = mEnvelopeCache.begin(); it != mEnvelopeCache.end(); )
    {
      if ( it->second.modelGeneration != model.generation() )
        it = mEnvelopeCache.erase( it );
      else
        ++it;
    }
  }

  const bool depthOk = depth.isValid() && layout.contentArea.height() > 0;

  // ---- depth interval selection: QGIS reuse (calculateOptimisedIntervals) ----
  mDepthIntervals = DepthIntervals();
  if ( depthOk )
  {
    const double pxPerMm = rc.scaleFactor() > 0 ? rc.scaleFactor() : ( 96.0 / 25.4 );
    mIntervalHost.setSize( QSizeF( layout.contentArea.width() / pxPerMm,
                                   layout.contentArea.height() / pxPerMm ) );
    mIntervalHost.setXMinimum( 0.0 );
    mIntervalHost.setXMaximum( std::max( 1.0, layout.contentArea.width() ) );
    mIntervalHost.setYMinimum( depth.minDepth() );
    mIntervalHost.setYMaximum( depth.maxDepth() );
    mIntervalHost.yAxis().setTextFormat( mStyle.labelTextFormat );
    mIntervalHost.yAxis().setLabelSuffix( QString() );
    mIntervalHost.calculateOptimisedIntervals( rc, mPlotContext );
    mDepthIntervals.label = mIntervalHost.yAxis().labelInterval();
    mDepthIntervals.major = mIntervalHost.yAxis().gridIntervalMajor();
    mDepthIntervals.minor = mIntervalHost.yAxis().gridIntervalMinor();
    mDepthIntervals.valid = mDepthIntervals.label > 0 && mDepthIntervals.major > 0;
  }

  // ---- prepare curves (slice + envelope, cached) ----
  struct PreparedTrack
  {
    const TrackGeometry *geometry = nullptr;
    std::shared_ptr<TrackSpec> spec;
    std::vector<const CurveSpec *> curves;
    std::vector<const std::vector<EnvelopeSample> *> envelopes;
  };
  std::vector<PreparedTrack> prepared;
  for ( const TrackGeometry &g : layout.tracks )
  {
    if ( g.role != TrackRole::CurveTrack )
      continue;
    std::shared_ptr<TrackSpec> spec = model.track( g.trackId );
    if ( !spec || spec->curves.empty() )
      continue;
    PreparedTrack pt;
    pt.geometry = &g;
    pt.spec = spec;
    const int bins = std::max( 1, static_cast<int>( std::lround( g.contentRect.height() ) ) );
    for ( const CurveSpec &curve : spec->curves )
    {
      if ( curve.data.isEmpty() )
        continue;
      qsizetype rawCount = 0;
      const std::vector<EnvelopeSample> &envelope = envelopeFor( model, curve, bins, depth, rawCount );
      pt.curves.push_back( &curve );
      pt.envelopes.push_back( &envelope );
      if ( stats )
      {
        stats->rawSamplesInSlices += rawCount;
        stats->envelopePoints += static_cast<qsizetype>( envelope.size() );
      }
    }
    prepared.push_back( std::move( pt ) );
  }

  const qint64 prepUsec = prepTimer.nsecElapsed() / 1000;

  // ============================ paint ============================
  QElapsedTimer paintTimer;
  paintTimer.start();

  // Horizontal depth grid across each curve track's content rect, drawn with
  // the QGIS grid symbols from the interval host's y axis.
  if ( depthOk && mDepthIntervals.valid )
  {
    QgsLineSymbol *majorSymbol = mIntervalHost.yAxis().gridMajorSymbol();
    QgsLineSymbol *minorSymbol = mIntervalHost.yAxis().gridMinorSymbol();
    const double dMin = depth.minDepth();
    const double dMax = depth.maxDepth();

    const bool drawMinor = mStyle.drawMinorDepthGrid && mDepthIntervals.minor > 0 &&
                           ( dMax - dMin ) / mDepthIntervals.minor < 20000;
    const bool drawMajor = ( dMax - dMin ) / mDepthIntervals.major < 20000;

    if ( majorSymbol )
      majorSymbol->startRender( rc );
    if ( minorSymbol )
      minorSymbol->startRender( rc );

    for ( const TrackGeometry &g : layout.tracks )
    {
      if ( g.role != TrackRole::CurveTrack )
        continue;
      const QRectF &r = g.contentRect;
      auto drawHLine = [ & ]( double value, QgsLineSymbol *symbol )
      {
        if ( !symbol )
          return;
        const double y = depth.yForDepth( value, r );
        if ( y < r.top() - 1 || y > r.bottom() + 1 )
          return;
        QPolygonF line;
        line << QPointF( r.left(), y ) << QPointF( r.right(), y );
        symbol->renderPolyline( line, nullptr, rc );
      };
      if ( drawMinor && minorSymbol )
      {
        for ( double v = std::ceil( dMin / mDepthIntervals.minor ) * mDepthIntervals.minor; v <= dMax;
              v += mDepthIntervals.minor )
          drawHLine( v, minorSymbol );
      }
      if ( drawMajor )
      {
        for ( double v = std::ceil( dMin / mDepthIntervals.major ) * mDepthIntervals.major; v <= dMax;
              v += mDepthIntervals.major )
          drawHLine( v, majorSymbol );
      }
    }

    if ( minorSymbol )
      minorSymbol->stopRender( rc );
    if ( majorSymbol )
      majorSymbol->stopRender( rc );
  }

  std::vector<PolylineRun> runs;  // scratch, reused per curve

  for ( const PreparedTrack &pt : prepared )
  {
    const TrackGeometry &g = *pt.geometry;
    const QRectF &content = g.contentRect;
    const TrackAxisSpec &axis = pt.spec->axis;

    painter->save();
    painter->setClipRect( content, Qt::IntersectClip );

    // ---- value grid (vertical lines) ----
    if ( mStyle.drawValueGrid && axis.isValid() && content.width() > 0 )
    {
      QgsPlotAxis *axisStyle = axis.style();
      const double vMin = axis.minimum;
      const double vMax = axis.maximum;
      auto drawVLine = [ & ]( double value )
      {
        const double x = axis.xForValue( value, content );
        if ( x < content.left() - 1 || x > content.right() + 1 )
          return;
        painter->setPen( QPen( QColor( 0, 0, 0, 45 ), 1.0 ) );
        painter->drawLine( QPointF( x, content.top() ), QPointF( x, content.bottom() ) );
      };
      if ( axis.scale == ValueScale::Log10 )
      {
        double decade = std::pow( 10.0, std::floor( std::log10( std::max( axis.logFloor, vMin ) ) ) );
        const double decadeMax = std::max( axis.logFloor, vMax );
        int guard = 0;
        while ( decade <= decadeMax && guard++ < 60 )
        {
          drawVLine( decade );
          if ( decade * 2.0 <= decadeMax )
            drawVLine( decade * 2.0 );
          if ( decade * 5.0 <= decadeMax )
            drawVLine( decade * 5.0 );
          decade *= 10.0;
        }
      }
      else if ( axisStyle && axisStyle->gridIntervalMajor() > 0 )
      {
        const double step = axisStyle->gridIntervalMajor();
        if ( ( vMax - vMin ) / step < 500 )
        {
          for ( double v = std::ceil( vMin / step ) * step; v <= vMax; v += step )
            drawVLine( v );
        }
      }
      else
      {
        // 5 evenly-placed reference lines when no interval is configured.
        for ( int i = 1; i < 5; ++i )
          drawVLine( vMin + ( vMax - vMin ) * i / 5.0 );
      }
    }

    // ---- generic depth interval bands ----
    for ( const DepthIntervalBand &band : pt.spec->bands )
    {
      const double yA = depth.yForDepth( std::min( band.top, band.bottom ), content );
      const double yB = depth.yForDepth( std::max( band.top, band.bottom ), content );
      if ( yB < content.top() || yA > content.bottom() )
        continue;
      const double topY = std::max( yA, content.top() );
      const double bottomY = std::min( yB, content.bottom() );
      QRectF bandRect( content.left(), topY, content.width(), std::max( 0.0, bottomY - topY ) );
      painter->fillRect( bandRect, band.fill );
      if ( !band.label.isEmpty() && bandRect.height() >= 10 )
      {
        QgsTextRenderer::drawText( QRectF( bandRect.left() + 3, bandRect.top() + 1, bandRect.width() - 6,
                                           bandRect.height() - 2 ),
                                   0.0, Qgis::TextHorizontalAlignment::Left, { band.label }, rc,
                                   mStyle.labelTextFormat, true,
                                   Qgis::TextVerticalAlignment::VerticalCenter );
      }
    }

    // ---- curves: fills, lines, markers ----
    for ( size_t ci = 0; ci < pt.curves.size(); ++ci )
    {
      const CurveSpec &curve = *pt.curves[ ci ];
      const std::vector<EnvelopeSample> &envelope = *pt.envelopes[ ci ];
      buildRuns( envelope, axis, depth, content, runs );

      if ( curve.style.fill != FillMode::None && !runs.empty() )
      {
        const QColor fill = fillColorWithOpacity( curve.style.fillColor, curve.style.fillOpacity );
        painter->setPen( Qt::NoPen );
        painter->setBrush( fill );
        if ( curve.style.fill == FillMode::ToBaseline )
        {
          const double baselineX = axis.xForValue( curve.style.fillBaseline, content );
          for ( const PolylineRun &run : runs )
          {
            if ( run.points.size() < 2 )
              continue;
            QPolygonF polygon = run.points;
            polygon << QPointF( baselineX, run.points.back().y() );
            polygon << QPointF( baselineX, run.points.front().y() );
            painter->drawPolygon( polygon );
          }
        }
        else // BetweenSeries
        {
          const CurveSpec *partner = nullptr;
          for ( const CurveSpec &candidate : pt.spec->curves )
          {
            if ( candidate.id == curve.partnerId )
            {
              partner = &candidate;
              break;
            }
          }
          if ( partner && !partner->data.isEmpty() )
          {
            for ( const PolylineRun &run : runs )
            {
              if ( run.points.size() < 2 )
                continue;
              QPolygonF polygon = run.points;
              for ( auto it = run.points.rbegin(); it != run.points.rend(); ++it )
              {
                const double partnerDepth = depth.depthAtY( it->y(), content );
                const double partnerValue = interpolateAtDepth( partner->data, partnerDepth );
                const double partnerX = axis.xForValue( partnerValue, content );
                if ( std::isfinite( partnerX ) )
                  polygon << QPointF( partnerX, it->y() );
              }
              painter->drawPolygon( polygon );
            }
          }
        }
      }

      if ( curve.style.lineColor.isValid() )
      {
        painter->setPen( QPen( curve.style.lineColor, curve.style.lineWidthF, curve.style.penStyle ) );
        QPainterPath path;
        for ( const PolylineRun &run : runs )
        {
          if ( run.points.isEmpty() )
            continue;
          path.moveTo( run.points.first() );
          for ( int i = 1; i < run.points.size(); ++i )
            path.lineTo( run.points[ i ] );
          if ( stats )
            ++stats->polylines;
        }
        painter->drawPath( path );
      }

      if ( curve.style.marker != MarkerShape::None && envelope.size() <= 1200 )
      {
        const QColor markerColor = curve.style.effectiveMarkerColor();
        for ( const PolylineRun &run : runs )
        {
          for ( const QPointF &p : run.points )
            drawMarkerShape( painter, curve.style.marker, p, curve.style.markerSizeF, markerColor );
        }
      }

      if ( stats )
      {
        for ( const EnvelopeSample &s : envelope )
        {
          if ( s.breakAfter )
            ++stats->subpathBreaks;
        }
      }
    }

    // ---- generic depth marker lines ----
    for ( const DepthMarkerLine &marker : pt.spec->markers )
    {
      const double y = depth.yForDepth( marker.depth, content );
      if ( y < content.top() || y > content.bottom() )
        continue;
      painter->setPen( QPen( marker.color, marker.widthF, marker.pen ) );
      painter->drawLine( QPointF( content.left(), y ), QPointF( content.right(), y ) );
      if ( !marker.label.isEmpty() )
      {
        const double textY = marker.labelAbove ? y - 14 : y + 2;
        QgsTextRenderer::drawText(
          QRectF( content.right() - 130, textY, 128, 12 ), 0.0,
          Qgis::TextHorizontalAlignment::Right, { marker.label }, rc, mStyle.labelTextFormat, true,
          Qgis::TextVerticalAlignment::Top );
      }
    }

    // ---- generic text anchors ----
    for ( const TextAnchor &text : pt.spec->texts )
    {
      const double y = depth.yForDepth( text.depth, content );
      if ( y < content.top() || y > content.bottom() )
        continue;
      QgsTextFormat format = mStyle.labelTextFormat;
      QColor c = text.color.isValid() ? text.color : mStyle.headerText;
      format.setColor( c );
      if ( text.sizeF > 0 )
      {
        QFont f = format.font();
        f.setPointSizeF( text.sizeF );
        format.setFont( f );
      }
      const double w = 140.0;
      const QRectF rect( text.leftSide ? content.left() + 2 : content.right() - w - 2, y - 6, w, 12 );
      QgsTextRenderer::drawText( rect, 0.0,
                                 text.leftSide ? Qgis::TextHorizontalAlignment::Left
                                               : Qgis::TextHorizontalAlignment::Right,
                                 { text.text }, rc, format, true,
                                 Qgis::TextVerticalAlignment::VerticalCenter );
    }

    painter->restore();

    // ---- header (outside content clip) ----
    if ( g.headerRect.height() > 0 )
    {
      painter->fillRect( g.headerRect, mStyle.headerBackground );
      painter->setPen( QPen( mStyle.separator, 1 ) );
      painter->drawLine( g.headerRect.bottomLeft(), g.headerRect.bottomRight() );

      QgsTextFormat titleFormat = mStyle.labelTextFormat;
      QColor tc = mStyle.headerText;
      titleFormat.setColor( tc );
      QString title = pt.spec->title;
      if ( !title.isEmpty() )
      {
        QgsTextRenderer::drawText( QRectF( g.headerRect.left() + 3, g.headerRect.top(),
                                           g.headerRect.width() - 6, g.headerRect.height() ),
                                   0.0, Qgis::TextHorizontalAlignment::Left, { title }, rc, titleFormat,
                                   true, Qgis::TextVerticalAlignment::VerticalCenter );
      }

      // Value scale annotation, right-aligned (min–max, log suffix).
      QString scaleText;
      if ( axis.isValid() )
      {
        const QgsPlotAxis *axisStyle = axis.style();
        scaleText = QStringLiteral( "%1 – %2" )
                      .arg( formatAxisValue( axisStyle, axis.minimum ),
                            formatAxisValue( axisStyle, axis.maximum ) );
        if ( axis.scale == ValueScale::Log10 )
          scaleText += QStringLiteral( " (log)" );
      }
      if ( !scaleText.isEmpty() && !title.isEmpty() && g.headerRect.width() > 160 )
      {
        QgsTextRenderer::drawText( QRectF( g.headerRect.left() + 3, g.headerRect.top(),
                                           g.headerRect.width() - 6, g.headerRect.height() ),
                                   0.0, Qgis::TextHorizontalAlignment::Right, { scaleText }, rc,
                                   titleFormat, true, Qgis::TextVerticalAlignment::VerticalCenter );
      }
    }
  }

  // ---- depth ruler track ----
  if ( depthOk && mDepthIntervals.valid )
  {
    for ( const TrackGeometry &g : layout.tracks )
    {
      if ( g.role != TrackRole::DepthRuler )
        continue;
      const QRectF &r = g.contentRect;
      const double dMin = depth.minDepth();
      const double dMax = depth.maxDepth();
      const double step = mDepthIntervals.label;
      painter->setPen( QPen( QColor( 0, 0, 0, 130 ), 1 ) );
      const QgsPlotAxis &hostAxis = mIntervalHost.yAxis();
      if ( ( dMax - dMin ) / step < 5000 )
      {
        for ( double v = std::ceil( dMin / step ) * step; v <= dMax; v += step )
        {
          const double y = depth.yForDepth( v, r );
          if ( y < r.top() - 1 || y > r.bottom() + 1 )
            continue;
          painter->drawLine( QPointF( r.right() - 5, y ), QPointF( r.right(), y ) );
          const QString label = formatAxisValue( &hostAxis, v );
          QgsTextRenderer::drawText( QRectF( r.left() + 2, y - 7, r.width() - 8, 14 ), 0.0,
                                     Qgis::TextHorizontalAlignment::Right, { label }, rc,
                                     mStyle.labelTextFormat, true,
                                     Qgis::TextVerticalAlignment::VerticalCenter );
        }
      }
    }
  }

  // ---- separators + border ----
  painter->setPen( QPen( mStyle.separator, 1 ) );
  for ( size_t i = 1; i < layout.tracks.size(); ++i )
  {
    const double x = layout.tracks[ i ].columnRect.left() - layout.separatorWidth / 2;
    painter->drawLine( QPointF( x, targetRect.top() ), QPointF( x, targetRect.bottom() ) );
  }
  painter->setPen( QPen( mStyle.border, 1 ) );
  painter->drawRect( targetRect );

  painter->restore();

  if ( stats )
  {
    stats->prepUsec = prepUsec;
    stats->paintUsec = paintTimer.nsecElapsed() / 1000;
  }
}

} // namespace geoviz::qgis_welltrack
