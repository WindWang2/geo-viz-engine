// Depth intervals (stratigraphy columns, lithology, facies, systems tract).
// The generic shape is: a set of named columns, each a list of categorized
// depth intervals. The 8-level WellIntervals of the Python package is a
// host-adapter concern — here columns are keyed, not enumerated.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace geoviz::well_track {

struct IntervalItem {
    double top = 0.0;
    double bottom = 0.0;
    std::string category;      // formation / lithology / facies name
    std::string description;   // optional long text (lithology descriptions)
};

struct IntervalColumn {
    std::string key;  // e.g. "system", "lithology", "phase"
    std::vector<IntervalItem> items;

    // Sorted-by-top copy built once per snapshot (performance plan §索引).
    // Call after the items are final; also computes maxLength_.
    void finalize();

    const std::vector<IntervalItem>& sorted() const { return sorted_; }

private:
    std::vector<IntervalItem> sorted_;
    double maxLength_ = 0.0;
    friend const IntervalItem* hitInterval(const IntervalColumn&, double);
};

struct IntervalSetData {
    std::vector<IntervalColumn> columns;

    const IntervalColumn* column(const std::string& key) const;
    void finalize();  // finalize every column
};

// Hit test: interval containing depth (top <= d < bottom). Among overlapping
// candidates the longest (bottom-top) wins — matching the label-paint rule
// where the visually dominant interval owns the readout. Null when gap.
const IntervalItem* hitInterval(const IntervalColumn& column, double depth);

// Interval visual shape. UpTriangle = TST, DownTriangle = HST
// (systems_tract.py _TRACT_SHAPES).
enum class IntervalShape : std::uint8_t {
    Rect,
    UpTriangle,
    DownTriangle,
};

struct IntervalStyle {
    std::uint32_t rgba = 0xFFD4E6F1;
    std::string patternKey;  // empty -> solid fill
    IntervalShape shape = IntervalShape::Rect;
};

}  // namespace geoviz::well_track
