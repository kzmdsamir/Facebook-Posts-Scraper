import type { Metadata } from "next";
import HistoryPage from "./page-content";

export const metadata: Metadata = {
  title: "History",
  description:
    "Every scraping run ever started, in order — reopen finished jobs for their full results and exports, or watch live ones land.",
};

export default function Page() {
  return <HistoryPage />;
}