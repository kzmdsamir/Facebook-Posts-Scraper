import type { Metadata } from "next";
import SettingsPage from "./page-content";

export const metadata: Metadata = {
  title: "Settings",
  description:
    "Appearance and default scraping options. Stored locally in your browser and overridable per run.",
};

export default function Page() {
  return <SettingsPage />;
}