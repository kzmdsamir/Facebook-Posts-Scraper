export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "chore",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "revert"
      ]
    ],
    "subject-min-length": [2, "always", 8],
    "subject-max-length": [2, "always", 120],
    "header-max-length": [2, "always", 150],
    "body-max-line-length": [1, "always", 200],
    "type-case": [2, "always", "lower-case"],
    "subject-case": [2, "never", ["start-case", "pascal-case", "upper-case"]],
    "scope-case": [2, "always", "lower-case"]
  },
  helpUrl: "https://github.com/conventional-changelog/commitlint/#readme"
};