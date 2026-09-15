import type { Metadata } from "next";
import InvestigationPage from "./page-content";

export const metadata: Metadata = {
  title: "Investigation",
  description:
    "Target, configure and run scraping jobs against public Facebook pages — with live progress, previews and JSON / CSV / Excel export.",
};

export default function Page() {
  return <InvestigationPage />;
}