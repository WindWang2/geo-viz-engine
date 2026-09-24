/***************************************************************************
 * geoviz-qgis-welltrack — well-track render model
 *
 * SPDX-License-Identifier: MIT
 *
 * Domain-neutral render snapshot: tracks (columns) × curves × generic
 * bands/markers/labels. Contains no well/lithology/facies semantics — those
 * belong to the host / B-line domain package, which maps its objects onto
 * these primitives.
 *
 * Ownership: WellTrackModel is ref-counted (shared_ptr) and hands out
 * shared_ptr<TrackSpec> so hosts can hold stable track handles. Series data
 * itself is NEVER owned here — CurveSeriesView borrows host memory whose
 * lifetime must cover every snapshot referencing it.
 *
 * Mutation bumps `generation()`; every kernel cache keys on it.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_TRACK_MODEL_H
#define GEOVIZ_QWT_TRACK_MODEL_H

#include "geoviz/qgis_welltrack/axis_spec.h"
#include "geoviz/qgis_welltrack/curve_data.h"
#include "geoviz/qgis_welltrack/curve_style.h"
#include "geoviz/qgis_welltrack/export.h"

#include <QBrush>
#include <QColor>
#include <QString>

#include <cstdint>
#include <memory>
#include <optional>
#include <vector>

namespace geoviz::qgis_welltrack
{

using SeriesId = quint64;
using TrackId = quint64;

//! Generic depth interval band spanning the whole track column
//  (fill + optional label). Pattern brushes are accepted — the kernel does
//  not interpret what the pattern means.
struct DepthIntervalBand
{
  double top = 0.0;       //!< shallower edge (depth units)
  double bottom = 0.0;    //!< deeper edge
  QBrush fill;
  QString label;
  QColor labelColor = Qt::black;
};

//! Generic horizontal line at a depth (e.g. a marker/top in domain terms).
struct DepthMarkerLine
{
  double depth = 0.0;
  QColor color = Qt::red;
  Qt::PenStyle pen = Qt::DashLine;
  double widthF = 1.0;
  QString label;
  bool labelAbove = true;
};

//! Generic text anchored at a depth.
struct TextAnchor
{
  double depth = 0.0;
  QString text;
  QColor color = Qt::black;
  double sizeF = 8.5;
  bool leftSide = true;
};

struct CurveSpec
{
  //! Must be unique within its track (the LOD cache is keyed on
  //! trackId+seriesId; collisions silently share envelopes).
  SeriesId id = 0;
  QString label;
  CurveSeriesView data;      //!< borrowed memory, never copied by the kernel
  CurveStyle style;
  SeriesId partnerId = 0;    //!< FillMode::BetweenSeries fill partner (0 = none)
};

enum class TrackRole
{
  CurveTrack,
  DepthRuler,                //!< depth label column (no curves rendered)
};

struct TrackSpec
{
  TrackId id = 0;
  QString title;
  TrackRole role = TrackRole::CurveTrack;
  bool visible = true;
  std::optional<double> fixedWidth;  //!< logical px; unset = stretch
  TrackAxisSpec axis;                //!< meaningful for CurveTrack only

  std::vector<CurveSpec> curves;
  std::vector<DepthIntervalBand> bands;
  std::vector<DepthMarkerLine> markers;
  std::vector<TextAnchor> texts;
};

class GEOVIZ_QWT_CORE_EXPORT WellTrackModel
{
  public:
    static std::shared_ptr<WellTrackModel> create();

    ~WellTrackModel();

    //! Appends a track with a fresh unique id; returns the shared handle.
    std::shared_ptr<TrackSpec> appendTrack( const QString &title,
                                            TrackRole role = TrackRole::CurveTrack );

    //! Inserts a track handle obtained from another model (snapshot reuse);
    //  the id is kept as-is. Returns false on duplicate id.
    bool adoptTrack( std::shared_ptr<TrackSpec> track );

    void removeTrack( TrackId id );
    std::shared_ptr<TrackSpec> track( TrackId id ) const;

    const std::vector<std::shared_ptr<TrackSpec>> &tracks() const { return mTracks; }
    std::vector<std::shared_ptr<TrackSpec>> &tracksForEdit() { return mTracks; }  //!< bumps generation on next touch()

    //! Monotonic mutation counter — cache key input for the whole kernel.
    quint64 generation() const { return mGeneration; }

    //! Marks the model mutated (call after editing a TrackSpec in place).
    void touch();

    //! Depth extent over all visible curve tracks' series (and bands);
    //  returns false when no finite data exists.
    bool depthExtent( double &outMin, double &outMax ) const;

  private:
    WellTrackModel();

    std::vector<std::shared_ptr<TrackSpec>> mTracks;
    quint64 mGeneration = 1;
    TrackId mNextTrackId = 1;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_TRACK_MODEL_H
