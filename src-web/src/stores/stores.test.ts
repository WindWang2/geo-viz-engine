import { act, renderHook } from "@testing-library/react";
import { useSettingsStore } from "./useSettingsStore";
import { useWellStore } from "./useWellStore";

beforeEach(() => {
  useSettingsStore.setState({ language: "zh" });
  useWellStore.setState({ wells: [], isLoading: false, error: null });
});

describe("useSettingsStore", () => {
  it("defaults language to zh", () => {
    const { result } = renderHook(() => useSettingsStore());
    expect(result.current.language).toBe("zh");
  });

  it("setLanguage updates language to en", () => {
    const { result } = renderHook(() => useSettingsStore());
    act(() => result.current.setLanguage("en"));
    expect(result.current.language).toBe("en");
  });

  it("setLanguage updates language back to zh", () => {
    const { result } = renderHook(() => useSettingsStore());
    act(() => result.current.setLanguage("en"));
    act(() => result.current.setLanguage("zh"));
    expect(result.current.language).toBe("zh");
  });
});

describe("useWellStore", () => {
  const mockWell = {
    well_id: "WELL-001",
    well_name: "Well 1",
    depth_start: 0,
    depth_end: 3000,
    curve_names: ["GR", "RT", "DEN", "NPHI"],
  };

  it("initial state has empty wells array", () => {
    const { result } = renderHook(() => useWellStore());
    expect(result.current.wells).toEqual([]);
  });

  it("initial isLoading is false", () => {
    const { result } = renderHook(() => useWellStore());
    expect(result.current.isLoading).toBe(false);
  });

  it("setWells stores well metadata", () => {
    const { result } = renderHook(() => useWellStore());
    act(() => result.current.setWells([mockWell]));
    expect(result.current.wells).toHaveLength(1);
    expect(result.current.wells[0].well_id).toBe("WELL-001");
  });

  it("clearWells empties the array", () => {
    const { result } = renderHook(() => useWellStore());
    act(() => result.current.setWells([mockWell]));
    act(() => result.current.clearWells());
    expect(result.current.wells).toHaveLength(0);
  });

  it("setLoading toggles loading state", () => {
    const { result } = renderHook(() => useWellStore());
    act(() => result.current.setLoading(true));
    expect(result.current.isLoading).toBe(true);
    act(() => result.current.setLoading(false));
    expect(result.current.isLoading).toBe(false);
  });

  it("setError stores error message", () => {
    const { result } = renderHook(() => useWellStore());
    act(() => result.current.setError("Network error"));
    expect(result.current.error).toBe("Network error");
  });

  it("setError null clears error", () => {
    const { result } = renderHook(() => useWellStore());
    act(() => result.current.setError("error"));
    act(() => result.current.setError(null));
    expect(result.current.error).toBeNull();
  });
});
