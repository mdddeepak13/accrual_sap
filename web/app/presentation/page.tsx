import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";

export const metadata = {
  title: "Accrual Engine — Presentation",
};

export default function PresentationPage() {
  return (
    <div className="flex h-dvh flex-col">
      <AppHeader />
      <div className="min-h-0 flex-1 bg-[#0f172a]">
        <iframe
          src="/presentation.html"
          className="h-full w-full border-0"
          title="Accrual Engine Presentation"
          allowFullScreen
        />
      </div>
      <AppFooter />
    </div>
  );
}
