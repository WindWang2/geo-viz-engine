/***************************************************************************
 * geoviz-qgis-welltrack — per-track value axis specification
 *
 * SPDX-License-Identifier: MIT
 *
 * Axis *math* lives here (linear/log10 mapping, degenerate handling). Axis
 * *styling* is delegated to QGIS's QgsPlotAxis (grid symbols, text format,
 * numeric format, suffix) so the kernel inherits QGIS rendering primitives
 * instead of reinventing them.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_AXIS_SPEC_H
#define GEOVIZ_QWT_AXIS_SPEC_H

#include "geoviz/qgis_welltrack/curve_style.h"
#include "geoviz/qgis_welltrack/export.h"

#include <qgsplot.h>

#include <QRectF>

#include <cmath>
#include <limits>
#include <memory>

namespace geoviz::qgis_welltrack
{

class GEOVIZ_QWT_CORE_EXPORT TrackAxisSpec
{
  public:
    double minimum = 0.0;
    double maximum = 1.0;
    ValueScale scale = ValueScale::Linear;

    //! Log-domain clamp floor (reference behavior: 1e-10, curve_track.py).
    double logFloor = 1e-10;

    //! QGIS-owned styling (grid line symbols, label text format, numeric
    //! format, label suffix). Lazily created; null means "renderer default".
    QgsPlotAxis *style() { return mStyle.get(); }
    const QgsPlotAxis *style() const { return mStyle.get(); }
    void setStyle( QgsPlotAxis *axis ) { mStyle.reset( axis ); }  //!< takes ownership
    QgsPlotAxis *ensureStyle();                                     //!< creates QGIS default if null

    bool isValid() const
    {
      return std::isfinite( minimum ) && std::isfinite( maximum ) && mappedMaximum() > mappedMinimum();
    }

    //! Raw value → axis unit (log10 for log scale, clamped to floor).
    double mapToUnit( double v ) const
    {
      if ( scale == ValueScale::Log10 )
      {
        if ( !std::isfinite( v ) )
          return v;
        if ( v < logFloor )
          v = logFloor;
        return std::log10( v );
      }
      return v;
    }

    //! Axis unit → raw value.
    double mapFromUnit( double u ) const
    {
      if ( scale == ValueScale::Log10 )
        return std::pow( 10.0, u );
      return u;
    }

    double mappedMinimum() const { return mapToUnit( minimum ); }
    double mappedMaximum() const { return mapToUnit( maximum ); }

    //! Value → x inside \a r. NaN in → NaN out. Degenerate range → center.
    double xForValue( double v, const QRectF &r ) const
    {
      const double u = mapToUnit( v );
      if ( !std::isfinite( u ) )
        return u;
      const double umin = mappedMinimum();
      const double umax = mappedMaximum();
      if ( umax - umin <= 0.0 )
        return r.left() + r.width() / 2.0;
      return r.left() + ( u - umin ) / ( umax - umin ) * r.width();
    }

    //! x → value (inverse of xForValue).
    double valueForX( double x, const QRectF &r ) const
    {
      if ( r.width() <= 0.0 )
        return std::numeric_limits<double>::quiet_NaN();
      const double umin = mappedMinimum();
      const double umax = mappedMaximum();
      if ( umax - umin <= 0.0 )
        return mapFromUnit( umin );
      const double u = umin + ( x - r.left() ) / r.width() * ( umax - umin );
      return mapFromUnit( u );
    }

  private:
    std::unique_ptr<QgsPlotAxis> mStyle;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_AXIS_SPEC_H
