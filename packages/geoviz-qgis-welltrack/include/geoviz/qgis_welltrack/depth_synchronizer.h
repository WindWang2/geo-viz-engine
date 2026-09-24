/***************************************************************************
 * geoviz-qgis-welltrack — multi-canvas depth synchronization (gui)
 *
 * SPDX-License-Identifier: MIT
 *
 * Mirrors geoviz_well_log's QPainterSyncManager contract: one canvas's
 * depth window propagates to the others exactly once per gesture (single
 * dispatcher flag + the canvas-side <1e-9 no-op guard break the feedback
 * loop).
 ***************************************************************************/
#ifndef GEOVIZ_QWT_DEPTH_SYNCHRONIZER_H
#define GEOVIZ_QWT_DEPTH_SYNCHRONIZER_H

#include "geoviz/qgis_welltrack/export.h"

#include <QObject>
#include <QPointer>

#include <vector>

namespace geoviz::qgis_welltrack
{

class WellTrackCanvas;

class GEOVIZ_QWT_GUI_EXPORT WellTrackSynchronizer : public QObject
{
    Q_OBJECT
  public:
    explicit WellTrackSynchronizer( QObject *parent = nullptr );
    ~WellTrackSynchronizer() override;

    void addCanvas( WellTrackCanvas *canvas );
    void removeCanvas( WellTrackCanvas *canvas );
    bool isEmpty() const { return mCanvases.empty(); }

  private slots:
    void onDepthRangeChanged( double shallow, double deep );

  private:
    std::vector<QPointer<WellTrackCanvas>> mCanvases;
    bool mDispatching = false;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_DEPTH_SYNCHRONIZER_H
