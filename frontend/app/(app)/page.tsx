"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { HomeView } from "@/components/home-view";

const HOW_IT_WORKS: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "Targets",
    body: "Paste public Facebook page or profile URLs — one per line. Each line is validated and normalized before the job starts.",
  },
  {
    title: "Filters",
    body: "Constrain the run with date ranges, post types, an optional post cap, or extra browser scroll rounds.",
  },
  {
    title: "Engines",
    body: "HTTP-only snapshots are fast and low-footprint; Browser mode goes through the page's own GraphQL feed for the full archive.",
  },
  {
    title: "Export",
    body: "Every extraction is written as JSON or CSV with honest counts — what you see in the summary matches the files on disk.",
  },
];

function HowItWorks() {
  return (
    <section className="mx-auto w-full max-w-5xl px-8" aria-label="How it works">
      <div className="pb-8 pt-10">
        <p className="font-sans font-light text-[10px] uppercase tracking-widest text-neutral-400">How it works</p>
        <ol className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map((step, index) => (
            <li key={step.title}>
              <p className="font-sans font-light text-[10px] tracking-widest text-neutral-600">
                Step {index + 1}: {step.title}
              </p>
              <p className="mt-2 font-sans text-sm font-light leading-relaxed text-neutral-600">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export default function HomePage() {
  const router = useRouter();

  const handleTrace = useCallback(
    (url: string) => {
      router.push(`/investigation?url=${encodeURIComponent(url)}`);
    },
    [router],
  );

  const handleAdvanced = useCallback(() => {
    router.push("/investigation");
  }, [router]);

  return (
    <div className="w-full animate-fade-in-up">
      <HomeView onTrace={handleTrace} onAdvanced={handleAdvanced} />
      <HowItWorks />
    </div>
  );
}