import { useTranslation } from "react-i18next";

const APP_VERSION = "0.1.0";

export default function StatusBar() {
  const { t } = useTranslation();

  return (
    <footer className="h-6 bg-geo-surface border-t border-geo-border flex items-center justify-between px-3 text-xs text-geo-muted flex-shrink-0">
      <span>{t("status.ready")}</span>
      <span>GeoViz Engine v{APP_VERSION}</span>
    </footer>
  );
}
