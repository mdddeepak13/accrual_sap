import { readFile } from "node:fs/promises";
import path from "node:path";

import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";
import { SlideViewer } from "@/components/slide-viewer";
import { parseSlides } from "@/lib/slides";

export const metadata = {
  title: "Accrual Engine — Presentation",
};

async function loadSlides(): Promise<string[]> {
  // Read the deck from the public folder so it's bundled with the deploy
  // and also downloadable at /presentation.md.
  const filePath = path.join(process.cwd(), "public", "presentation.md");
  const markdown = await readFile(filePath, "utf8");
  return parseSlides(markdown);
}

export default async function PresentationPage() {
  const slides = await loadSlides();
  return (
    <div className="flex h-dvh flex-col">
      <AppHeader />
      <div className="min-h-0 flex-1">
        <SlideViewer slides={slides} />
      </div>
      <AppFooter />
    </div>
  );
}
