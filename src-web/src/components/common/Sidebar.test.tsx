import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../../i18n";
import Sidebar from "./Sidebar";

function renderSidebar(path = "/") {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe("Sidebar", () => {
  beforeAll(() => i18n.changeLanguage("zh"));

  it("renders Home nav link", () => {
    renderSidebar();
    expect(screen.getByText("首页")).toBeInTheDocument();
  });

  it("renders Well Log nav link", () => {
    renderSidebar();
    expect(screen.getByText("测井可视化")).toBeInTheDocument();
  });

  it("home link points to /", () => {
    renderSidebar();
    expect(screen.getByText("首页").closest("a")).toHaveAttribute("href", "/");
  });

  it("well-log link points to /well-log", () => {
    renderSidebar();
    expect(screen.getByText("测井可视化").closest("a")).toHaveAttribute("href", "/well-log");
  });
});
