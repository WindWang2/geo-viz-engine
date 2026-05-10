import json
from .payload_builder import build_merged_curve_track


class TrackManager:
    """Manages track ordering, visibility, merge/split for a well log chart."""

    def __init__(self, track_pool: dict[str, dict]):
        self._pool: dict[str, dict] = dict(track_pool)

    @property
    def pool(self) -> dict[str, dict]:
        return self._pool

    def resolve_sorted_tracks(
        self, display_items: list[tuple[str, bool]]
    ) -> list[dict]:
        """Resolve display items into a flat list of track descriptors.

        Args:
            display_items: list of (display_text, is_checked) in display order.

        Returns:
            Ordered list of track descriptor dicts ready for ECharts.
        """
        sorted_tracks = []
        for text, checked in display_items:
            if not checked:
                continue
            sorted_tracks.extend(self._resolve_item(text))
        return sorted_tracks

    def build_payload(
        self,
        metadata: dict,
        display_items: list[tuple[str, bool]],
    ) -> str:
        """Build the full JSON payload for ChartEngine.render_data()."""
        tracks = self.resolve_sorted_tracks(display_items)
        return json.dumps({"metadata": metadata, "tracks": tracks})

    def merge_curves(self, name1: str, name2: str) -> dict:
        """Merge two curve tracks into one. Returns the merged descriptor."""
        merged = build_merged_curve_track(self._pool, [name1, name2])
        return merged

    def split_curves(self, merged_name: str) -> tuple[dict, dict]:
        """Split a merged curve track back into two individual tracks.

        Args:
            merged_name: slash-separated name like "AC/GR"

        Returns:
            Tuple of (track1, track2) descriptors.
        """
        parts = [p.strip() for p in merged_name.split("/")]
        if len(parts) != 2:
            raise ValueError(f"Cannot split non-merged track: {merged_name}")
        t1 = self._pool.get(parts[0])
        t2 = self._pool.get(parts[1])
        if t1 is None or t2 is None:
            raise ValueError(f"Split targets not found in pool: {parts}")
        return t1, t2

    def _resolve_item(self, text: str) -> list[dict]:
        """Resolve a single display item text to track descriptor(s)."""
        # Direct pool key
        if text in self._pool:
            return [self._pool[text]]

        # Group: 地层系统
        if "地层系统" in text:
            result = []
            for k in ["系", "统", "组"]:
                if k in self._pool:
                    result.append(self._pool[k])
            return result

        # Group: 沉积相
        if "沉积相" in text:
            result = []
            for k in ["微相", "亚相", "相"]:
                if k in self._pool:
                    result.append(self._pool[k])
            return result

        # Merged curves with +
        if "+" in text:
            curve_names = [c.strip() for c in text.split("+")]
            if len(curve_names) == 2:
                c1, c2 = curve_names
                if c1 in self._pool and c2 in self._pool:
                    return [build_merged_curve_track(self._pool, [c1, c2])]

        # "曲线: XXX" prefix
        if text.startswith("曲线: "):
            curves_part = text.replace("曲线: ", "")
            curve_names = [c.strip() for c in curves_part.split("+")]
            if len(curve_names) == 1:
                c_name = curve_names[0]
                if c_name in self._pool:
                    return [self._pool[c_name]]
            elif len(curve_names) == 2:
                c1, c2 = curve_names
                if c1 in self._pool and c2 in self._pool:
                    return [build_merged_curve_track(self._pool, [c1, c2])]

        # Depth shorthand
        if "深度" in text and "深度" in self._pool:
            return [self._pool["深度"]]

        # Fallback: fuzzy match
        result = []
        for k in self._pool:
            if k in text and self._pool[k] not in result:
                result.append(self._pool[k])
        return result

    def add_tracks(self, tracks: dict[str, dict]):
        self._pool.update(tracks)

    def remove_tracks(self, names: list[str]):
        for n in names:
            self._pool.pop(n, None)
