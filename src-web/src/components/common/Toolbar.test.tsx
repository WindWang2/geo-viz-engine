import { render, screen, fireEvent } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../i18n";
import Toolbar from "./Toolbar";

describe("Toolbar", () => {
  beforeEach(() => i18n.changeLanguage("zh"));

  it("renders app title", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <Toolbar />
      </I18nextProvider>
    );
    expect(screen.getByText("GeoViz Engine")).toBeInTheDocument();
  });

  it("renders language toggle button", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <Toolbar />
      </I18nextProvider>
    );
    expect(screen.getByRole("button", { name: /English/i })).toBeInTheDocument();
  });

  it("clicking language button switches to English", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <Toolbar />
      </I18nextProvider>
    );
    const langBtn = screen.getByRole("button", { name: /English/i });
    fireEvent.click(langBtn);
    expect(i18n.language).toBe("en");
  });
});
