# Implementation Plan: Landing Page Redesign ("The Overlook")

Source spec: `docs/superpowers/specs/2026-08-08-landing-page-overlook-design.md`

Scope: `quiz/templates/quiz/landing.html`, `static/css/landing.css` only.

## Task 1: Palette, nav, and hero

**Goal:** Establish the new visual foundation and rebuild the nav + hero
section.

**Context:** The current file uses a "Scholastic Utopian" cream/gold palette
with a multi-orb gradient hero, anchor-link nav, and a hamburger mobile menu.
All of that is being replaced.

**Approach:**
- Replace the `:root` design tokens in `landing.css` with the "Deep Sea +
  Warm Amber Pop" palette from the spec
- Rebuild `.nav`: logo + auth controls only, no anchor links, no hamburger
  markup/JS/CSS; keep the existing scroll-based `.nav.scrolled` transition
  mechanism
- Rebuild `.hero`: full-bleed `background-image` using
  `{% static 'images/landing-page-image.webp' %}`, `background-size: cover`,
  gradient scrim (vertical on mobile, horizontal on desktop), monospace
  `TRANSMISSION 01` label, headline, two CTAs (`quiz:session_landing`,
  `quiz:gallery`)
- Remove now-unused CSS: gradient orbs, grid overlay, hero-visual floating
  cards, hero stats bar, hamburger/mobile-menu styles
- Remove now-unused JS: hamburger toggle listeners (keep scroll-reveal
  `IntersectionObserver` and nav-scroll listener, both still used later)

**Acceptance criteria:**
- Page renders with the new hero image as a full-bleed background at mobile
  and desktop widths
- Nav shows logo + Sign In/Sign Up (or user email + Sign Out when
  authenticated) with no anchor links or hamburger, at all viewport widths
- Nav becomes solid/opaque after scrolling past the hero
- Hero contains a working link to `quiz:session_landing` and a working link
  to `quiz:gallery`

**Verify:** `uv run manage.py runserver`, view `/` at ~390px and ~1440px
widths (or use browser-verify), confirm hero image loads and nav behaves as
described above.

## Task 2: Manifesto, showcase, choose-your-path, footer

**Goal:** Build the remaining below-the-fold sections.

**Context:** Depends on Task 1's palette tokens.

**Approach:**
- `.manifesto` section: solid `--ov-navy-mid` background, centered italic
  quote, `02 / MANIFESTO` label, reuse the existing SVG-turbulence noise
  `::after` technique from the current `.philosophy` section
- `.showcase` section: `03 / A PEEK AT THE GAMES` label, 2-3 framed
  "monitor window" panels (bezel + chrome dots + inner placeholder image
  slot), alternating slight rotation, stacked on mobile / staggered row on
  desktop
- `.paths` section: `04 / CHOOSE YOUR PATH` label, three cards with distinct
  accent border colors, linking to `quiz:session_landing`, `quiz:gallery`,
  `quiz:analytics` respectively
- Footer: logo/wordmark, one tagline line, copyright line only - no link
  columns
- Remove now-unused CSS from the old file: `.philosophy` (old palette
  version), `.features`, `.how-it-works`/`.steps`, `.differentiator`,
  `.cta`, old `.footer-links` grid
- Wire the new sections' animated elements into the existing
  `IntersectionObserver` reveal script (update the querySelector list)

**Acceptance criteria:**
- All three required links (`quiz:session_landing`, `quiz:gallery`,
  `quiz:analytics`) are present and correct within the "Choose Your Path"
  section
- Manifesto, showcase, and path sections scroll-reveal using the existing
  observer pattern
- No leftover CSS rules target removed markup (no dead selectors for
  `.feature-card`, `.step`, `.diff-card`, etc.)

**Verify:** Manual scroll-through at mobile and desktop widths; confirm all
three links resolve via `{% url %}` without template errors
(`uv run manage.py runserver`, hit `/` and click each of the three path
links).

## Task 3: Responsive polish and cleanup

**Goal:** Mobile-first pass and final cleanup.

**Context:** Mobile is the primary access path per the spec.

**Approach:**
- Review every section at common breakpoints (375px, 768px, 1024px,
  1440px), adjusting `background-position` on the hero and spacing/type
  scale as needed
- Confirm the showcase and path sections collapse to single column below
  the existing `768px` breakpoint used elsewhere in the file
- Sweep `landing.css` for any remaining dead rules tied to removed
  sections/markup
- Sanity-check `black --check` is unaffected (no Python changes expected)

**Acceptance criteria:**
- Page is legible and well-spaced at all four reference widths with no
  horizontal overflow
- No unused CSS selectors remain for markup that no longer exists in
  `landing.html`
- `uv run black . --check` passes

**Verify:** Manual resize/DevTools device toolbar pass at the four
reference widths; `uv run black . --check`.
