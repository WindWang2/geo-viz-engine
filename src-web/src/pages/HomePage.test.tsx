import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18n";
import HomePage from "./HomePage";

function renderPage() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe("HomePage", () => {
  beforeAll(() => i18n.changeLanguage("zh"));

  it("renders welcome heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders description text", () => {
    renderPage();
    expect(screen.getByText("专业地质数据可视化平台")).toBeInTheDocument();
  });

  it("renders link to well-log page", () => {
    renderPage();
    const link = screen.getByText("开始测井分析").closest("a");
    expect(link).toHaveAttribute("href", "/well-log");
  });
});
