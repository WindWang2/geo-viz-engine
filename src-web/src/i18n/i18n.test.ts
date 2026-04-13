import i18n from "./index";

describe("i18n configuration", () => {
  it("defaults to Chinese (zh)", () => {
    expect(i18n.language).toBe("zh");
  });

  it("translates app title in Chinese", () => {
    i18n.changeLanguage("zh");
    expect(i18n.t("app.title")).toBe("GeoViz Engine");
  });

  it("translates nav.wellLog in Chinese", () => {
    i18n.changeLanguage("zh");
    expect(i18n.t("nav.wellLog")).toBe("测井可视化");
  });

  it("translates nav.home in English after language change", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("nav.home")).toBe("Home");
  });

  it("translates nav.wellLog in English", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("nav.wellLog")).toBe("Well Log");
  });

  it("translates status.ready in Chinese", async () => {
    await i18n.changeLanguage("zh");
    expect(i18n.t("status.ready")).toBe("就绪");
  });

  it("translates status.ready in English", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("status.ready")).toBe("Ready");
  });

  it("translates page.wellLog.generateData in Chinese", async () => {
    await i18n.changeLanguage("zh");
    expect(i18n.t("page.wellLog.generateData")).toBe("生成合成数据");
  });

  afterAll(async () => {
    await i18n.changeLanguage("zh");
  });
});
