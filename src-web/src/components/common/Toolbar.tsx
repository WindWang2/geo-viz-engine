import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/useSettingsStore";

export default function Toolbar() {
  const { t } = useTranslation();
  const { language, setLanguage } = useSettingsStore();

  const otherLang = language === "zh" ? "en" : "zh";
  const otherLangLabel = t(`lang.${otherLang}`);

  return (
    <header className="h-9 bg-geo-surface border-b border-geo-border flex items-center justify-between px-4 flex-shrink-0">
      <span className="text-sm font-medium text-geo-text tracking-wide">
        {t("app.title")}
      </span>
      <button
        onClick={() => setLanguage(otherLang)}
        className="text-xs text-geo-muted hover:text-geo-text transition-colors px-2 py-1 rounded hover:bg-white/5"
      >
        {otherLangLabel}
      </button>
    </header>
  );
}
