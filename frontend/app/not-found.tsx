import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata: Metadata = {
  title: "404 · Page not found",
  description: "This page could not be found.",
};

export default function NotFound() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center px-6 py-24"
      style={{ backgroundColor: "#1e1e2e", color: "#cdd6f4" }}
    >
      <p
        className="font-mono text-[10px] uppercase tracking-[0.3em]"
        style={{ color: "#7fb8b1" }}
        aria-hidden="true"
      >
        error · not found
      </p>

      <h1
        className="font-sans text-7xl font-semibold tracking-tighter sm:text-8xl"
        style={{ color: "#cdd6f4" }}
      >
        4<span style={{ color: "#7fb8b1" }}>0</span>4
      </h1>

      <p className="mt-4 max-w-md text-center text-sm leading-relaxed" style={{ color: "#a6adc8" }}>
        This page drifted off the timeline. The post you&apos;re looking for either never existed or
        was scrubbed — check the URL, or head back to the dashboard.
      </p>

      <div
        className="mt-10 h-px w-24"
        style={{ backgroundColor: "#7fb8b1", opacity: 0.4 }}
        aria-hidden="true"
      />

      <nav className="mt-10 flex items-center gap-6">
        <Link
          href="/"
          className="group inline-flex items-center gap-2 border px-4 py-2 text-xs uppercase tracking-[0.2em] transition-colors"
          style={{ borderColor: "#45475a", color: "#cdd6f4" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
          <span className="group-hover:underline">Back to dashboard</span>
        </Link>
        <Link
          href="/docs"
          className="text-xs uppercase tracking-[0.2em] transition-colors"
          style={{ color: "#7fb8b1" }}
        >
          Read the docs
        </Link>
      </nav>

      <p className="mt-16 font-mono text-[10px] tracking-[0.2em] uppercase" style={{ color: "#6c7086" }}>
        facebook posts scraper · 404 boundary
      </p>
    </main>
  );
}