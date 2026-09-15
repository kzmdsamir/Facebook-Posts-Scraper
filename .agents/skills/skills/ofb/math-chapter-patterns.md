# Mathematics chapter patterns

Use these conventions in `core.html` and `supplement.html` so every math chapter looks and behaves the same. Shared styles live in [`content/math/subject.scss`](../../content/math/subject.scss); shared setup in [`content/math/subject.ts`](../../content/math/subject.ts).

## Prose and sections

- Wrapper: `<div class="book-prose">`
- Section titles: `<h2 id="…" class="book-prose__heading">`
- In-chapter links: plain `<a href="/math/…/">` inside `.book-prose` (theme styles them)
- For chained calculations, prefer aligned multi-line KaTeX:

```html
<p class="book-formula">\[
  \begin{aligned}
    b &= \sqrt{c^2-a^2} \\
      &= \sqrt{13^2-5^2} \\
      &= \sqrt{144} \\
      &= 12
  \end{aligned}
\]</p>
```

This keeps equal signs aligned and avoids long single-line equations on mobile.

## Checkpoints (required shape)

Copy from any live chapter supplement (e.g. `content/math/basic-math-notation/supplement.html`):

```html
<h2 id="checkpoints" class="book-prose__heading">Checkpoints</h2>
<details class="book-question">
  <summary class="book-question__prompt">Your question here.</summary>
  <div class="book-question__solution">
    <p><strong>Answer:</strong> …</p>
  </div>
</details>
```

Do **not** use `book-question__answer` — only `book-question__solution` is styled.

## Dot pictures

- Use `counting-dots`, `counting-dots__dot`, `counting-dots--empty`, `counting-dots__none` for amount pictures (see `counting-and-numbers`).
- Use `notation-dots` for smaller chains in notation chapters.

## Widgets

- Mount: `<div class="math-widget-mount" data-widget="widget-name" data-pagefind-ignore></div>`
- Widget file: `widgets/widget-name.tsx` with default export

## Chapter-only CSS

Put styles used in **one** chapter under `chapter.scss`. Move duplicated blocks into `subject.scss` instead.
