import type { MetadataRoute } from "next";
import { DOCS_PAGES } from "@/lib/docs-meta";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${BASE_URL}/investigation`, lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: `${BASE_URL}/history`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE_URL}/accounts`, lastModified: now, changeFrequency: "monthly", priority: 0.4 },
    { url: `${BASE_URL}/settings`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${BASE_URL}/docs`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
  ];

  const docRoutes: MetadataRoute.Sitemap = DOCS_PAGES.filter((page) => page.slug !== "overview").map((page) => ({
    url: `${BASE_URL}/docs/${page.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }));

  return [...staticRoutes, ...docRoutes];
}
