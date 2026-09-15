import type { Metadata } from "next";
import AccountsPage from "./page-content";

export const metadata: Metadata = {
  title: "Accounts",
  description:
    "Manage saved browser login sessions for public scraping. Only metadata is shown — cookie contents are never exposed.",
};

export default function Page() {
  return <AccountsPage />;
}