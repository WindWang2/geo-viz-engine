import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { vi } from "vitest";
import i18n from "../i18n";
import WellLogPage from "./WellLogPage";

const mockRequest = vi.fn().mockResolvedValue({
  generated_count: 3,
  wells: [
    { well_id: "WELL-001", well_name: "Well 1", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
    { well_id: "WELL-002", well_name: "Well 2", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
    { well_id: "WELL-003", well_name: "Well 3", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
  ],
  message: "Generated 3 synthetic wells",
});

vi.mock("../hooks/useApi", () => ({
  useApi: () => ({
    request: mockRequest,
    loading: false,
    error: null,
  }),
}));

function renderPage() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>
        <WellLogPage />
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe("WellLogPage", () => {
  beforeAll(() => i18n.changeLanguage("zh"));

  it("renders page title", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: /测井可视化/i })).toBeInTheDocument();
  });

  it("renders generate data button", async () => {
    renderPage();
    expect(await screen.findByRole("button", { name: /生成合成数据/i })).toBeInTheDocument();
  });

  it("shows no-data message initially when wells store is empty", async () => {
    renderPage();
    expect(await screen.findByText(/暂无数据/i)).toBeInTheDocument();
  });
});
