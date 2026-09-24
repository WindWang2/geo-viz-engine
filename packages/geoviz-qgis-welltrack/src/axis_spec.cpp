/***************************************************************************
 * geoviz-qgis-welltrack — axis spec helpers
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "axis_spec.h"

namespace geoviz::qgis_welltrack
{

QgsPlotAxis *TrackAxisSpec::ensureStyle()
{
  if ( !mStyle )
    mStyle = std::make_unique<QgsPlotAxis>();  // QGIS defaults: numeric format + grid symbols
  return mStyle.get();
}

} // namespace geoviz::qgis_welltrack
