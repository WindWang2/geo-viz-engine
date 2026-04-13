import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Activity } from "lucide-react";

export default function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
      <div className="max-w-lg">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-geo-accent/20 rounded-2xl flex items-center justify-center">
            <Activity size={32} className="text-geo-accent" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-geo-text mb-3">
          {t("page.home.title")}
        </h1>
        <p className="text-geo-muted mb-8">
          {t("page.home.description")}
        </p>
        <Link
          to="/well-log"
          className="inline-flex items-center gap-2 bg-geo-accent hover:bg-geo-accent/80 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          <Activity size={16} />
          {t("page.home.startWellLog")}
        </Link>
      </div>
    </div>
  );
}
