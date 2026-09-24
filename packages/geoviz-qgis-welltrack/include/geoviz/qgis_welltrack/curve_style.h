/***************************************************************************
 * geoviz-qgis-welltrack — curve rendering style
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#ifndef GEOVIZ_QWT_CURVE_STYLE_H
#define GEOVIZ_QWT_CURVE_STYLE_H

#include <QColor>
#include <QtGlobal>

namespace geoviz::qgis_welltrack
{

enum class ValueScale
{
  Linear,
  Log10,
};

enum class FillMode
{
  None,
  ToBaseline,      //!< fill between curve and a fixed baseline value (axis units)
  BetweenSeries,   //!< fill between this curve and CurveSpec::partnerId
};

enum class MarkerShape
{
  None,
  Circle,
  Square,
  Diamond,
  Cross,
};

struct CurveStyle
{
  QColor lineColor = Qt::darkBlue;
  double lineWidthF = 1.0;
  Qt::PenStyle penStyle = Qt::SolidLine;

  MarkerShape marker = MarkerShape::None;
  double markerSizeF = 3.0;
  QColor markerColor;          //!< invalid → lineColor

  FillMode fill = FillMode::None;
  double fillBaseline = 0.0;   //!< axis units, ToBaseline only
  QColor fillColor;
  qreal fillOpacity = 0.25;

  QColor effectiveMarkerColor() const { return markerColor.isValid() ? markerColor : lineColor; }
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_CURVE_STYLE_H
