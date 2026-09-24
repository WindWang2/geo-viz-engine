/***************************************************************************
 * geoviz-qgis-welltrack — export macros
 *
 * SPDX-License-Identifier: MIT
 *
 * Two libraries share this header: the core (no QtWidgets) and the gui
 * (QgsPlotCanvas stack). Both are built from this package.
 ***************************************************************************/
#ifndef GEOVIZ_QGIS_WELLTRACK_EXPORT_H
#define GEOVIZ_QGIS_WELLTRACK_EXPORT_H

#include <QtGlobal>

#if defined(GEOVIZ_QWT_STATIC)
#  define GEOVIZ_QWT_CORE_EXPORT
#  define GEOVIZ_QWT_GUI_EXPORT
#else
#  if defined(GEOVIZ_QWT_CORE_LIBRARY)
#    define GEOVIZ_QWT_CORE_EXPORT Q_DECL_EXPORT
#  else
#    define GEOVIZ_QWT_CORE_EXPORT Q_DECL_IMPORT
#  endif
#  if defined(GEOVIZ_QWT_GUI_LIBRARY)
#    define GEOVIZ_QWT_GUI_EXPORT Q_DECL_EXPORT
#  else
#    define GEOVIZ_QWT_GUI_EXPORT Q_DECL_IMPORT
#  endif
#endif

#endif // GEOVIZ_QGIS_WELLTRACK_EXPORT_H
