import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../i18n";
import StatusBar from "./StatusBar";

describe("StatusBar", () => {
  beforeAll(() => i18n.changeLanguage("zh"));

  it("renders ready status text", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <StatusBar />
      </I18nextProvider>
    );
    expect(screen.getByText("就绪")).toBeInTheDocument();
  });

  it("renders version string", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <StatusBar />
      </I18nextProvider>
    );
    expect(screen.getByText(/v0\.1\.0/)).toBeInTheDocument();
  });
});
