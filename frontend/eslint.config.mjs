import { defineConfig, globalIgnores } from "eslint/config";
import coreWebVitals from "eslint-config-next/core-web-vitals";
import eslintConfigTypescript from "eslint-config-next/typescript";

export default defineConfig([
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "node_modules/**",
    "next-env.d.ts",
  ]),
  ...coreWebVitals,
  ...eslintConfigTypescript,
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      // These two are intentionally relaxed in this project:
      //
      // react/no-unescaped-entities — the docs (app/docs/content.tsx) and
      // several components are prose-heavy; escaping every apostrophe and
      // quote as &apos;/&quot; mangles readability without adding safety.
      // Quotes in JSX text are valid; the rule is cosmetic.
      //
      // react-hooks/set-state-in-effect — an aggressive new rule from
      // eslint-plugin-react-hooks@7. It flags legitimate patterns used
      // across the app: hydration gates (setMounted), prop->state sync
      // (drawer closes on route change), and async loaders that only set
      // state after `await`. Enforcing it would force contorted rewrites
      // of correct code.
      "react/no-unescaped-entities": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);