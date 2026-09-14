import type { Metadata } from "next";
import HomePage from "./page-content";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Scrape publicly available Facebook page and profile posts. Track progress live, preview results, and export to JSON, CSV or Excel.",
};

export default function Page() {
  return <HomePage />;
}