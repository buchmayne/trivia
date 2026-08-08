# Landing Page Redesign: "The Overlook"

Date: 2026-08-08
Branch: `refactor-landing-page`
Status: Approved by user, ready for implementation planning

## Summary

Replace the current SaaS-style landing page (`quiz/templates/quiz/landing.html` /
`static/css/landing.css`) with a shorter, more editorial, image-led design built
around a single new hero image (`static/images/landing-page-image.webp`): a
surreal photo of a person at a vintage computer desk overlooking a cresting
ocean wave. This is a passion project, not a commercial product, and the new
design should read that way - fewer sections, more mood, less "convert the
visitor" pressure.

## Scope

**In scope:**
- `quiz/templates/quiz/landing.html`
- `static/css/landing.css`
- Any new small supporting assets needed purely for this page (none currently
  anticipated beyond the existing hero image)

**Out of scope (must not change):**
- Gallery view, session/live-game views, analytics view, and all other
  templates/CSS/JS
- All URL routing, auth flows, and backend logic
- The three functional links that currently live on the landing page must
  continue to exist somewhere on the redesigned page:
  - a link to the session/host flow (`quiz:session_landing`)
  - a link to the gallery (`quiz:gallery`)
  - a link to analytics (`quiz:analytics`)

No existing automated tests target `quiz/landing.html` directly (confirmed via
search of `quiz/tests/` and `e2e/`), so there are no test contracts to
preserve for this template beyond it rendering successfully and containing
those three links.

## Design Direction

**Concept: "The Overlook"** - one full-bleed hero image, followed by a small
number of lean, text-forward sections on a solid dark background. The mood is
carried through color, typography, and spacing rather than additional
imagery. Structured like a short scroll narrative ending in a deliberate
three-way choice, rather than a typical marketing funnel.

Copy throughout is placeholder for this pass - the focus is nailing the
visual design first. Placeholder copy should be clearly usable as real copy
later without restructuring the layout (i.e., realistic length, not lorem
ipsum).

### Color Palette - "Deep Sea + Warm Amber Pop"

Sampled from the hero image, plus one warm accent for interactive elements:

| Token | Hex | Use |
|---|---|---|
| `--ov-navy-deep` | `#141b33` | Primary background (manifesto, showcase sections) |
| `--ov-navy-mid` | `#1a2140` | Card/panel surfaces |
| `--ov-ink` | `#0a0e1f` | Footer, deepest surfaces |
| `--ov-blue-mid` | `#344276` | Secondary panel borders/accents |
| `--ov-blue-glow` | `#5370c4` | CRT-glow blue accent (links, secondary highlights) |
| `--ov-mist` | `#8a9fd4` | Muted blue text (labels, secondary headings) |
| `--ov-cream` | `#f4efe4` | Primary text on dark backgrounds |
| `--ov-amber` | `#d9a463` | Primary accent - CTAs, active states, key highlights |
| `--ov-amber-dark` | `#b87d3f` | Amber hover state |

This replaces the current "Scholastic Utopian" cream/gold-on-cream palette
entirely on this page. Other pages are unaffected since this palette lives
only in `landing.css`.

### Typography

Keep the existing font stack - it already fits the desired mood:
- **Fraunces** (display serif) - headlines, quote text
- **Lora** (body serif) - body copy
- **JetBrains Mono** - small labels, section markers, terminal-style accents
  (new, expanded usage vs. current page)

### Terminal Accents

Small details borrowed from a "retro terminal" motif (not a full theme
change) to tie into the vintage computer in the hero image:
- Monospace section labels styled like transmission/log entries, e.g.
  `TRANSMISSION 01`, `02 / MANIFESTO`
- A small dot/indicator glyph before labels
- Framed "monitor window" treatment for the screenshot showcase (see below)

## Page Structure

Single scrolling page, five sections plus nav and footer:

### 1. Navigation

- Fixed/sticky, transparent over the hero, becomes a solid dark bar
  (`--ov-ink` at ~95% opacity + blur) once scrolled past the hero - same
  scroll-based mechanism as the current page (`.nav.scrolled`)
- Contents: logo mark + wordmark on the left; auth state on the right
  (Sign In / Sign Up, or user email + Sign Out when authenticated) - same
  conditional logic as today
- **No hamburger menu, no anchor nav links.** There are no mid-page anchor
  destinations anymore (Features/How It Works sections are gone), so the nav
  has nothing to collapse. It stays as a simple inline row at all
  viewport widths, with auth controls sized down on narrow screens.

### 2. Hero ("The Overlook")

- Full-bleed background image using `background-size: cover`, cropped
  (Option A from earlier review)
- `background-position` tuned to keep the person/desk/wave transition
  roughly centered so the crop stays reasonable from mobile through desktop
  (mobile crops very little given the image's portrait aspect ratio is close
  to phone viewports; desktop crops more aggressively but keeps the
  focal area)
- Dark gradient scrim over the image for text legibility:
  - Mobile: vertical gradient, transparent top to `--ov-ink` at ~85% at the
    bottom, where the text sits
  - Desktop: horizontal gradient, dark on the left (where text sits) fading
    to transparent on the right (where more of the image is visible)
- Content (bottom-left on mobile, left-aligned mid-height on desktop):
  - Small monospace label: `TRANSMISSION 01`
  - Headline (placeholder): "Where Curiosity / *Comes to Play*" (italic
    accent line in `--ov-mist`)
  - Two CTA buttons:
    - Primary (amber fill): "Host a Game" -> `quiz:session_landing`
    - Secondary (outline): "Explore" -> `quiz:gallery`
- No stats bar, no floating card decorations (removed - they belonged to the
  old SaaS-y hero)

### 3. Manifesto

- Solid `--ov-navy-mid` background, no imagery
- Centered, generous vertical padding
- Small monospace label: `02 / MANIFESTO`
- One short italic serif quote (placeholder, realistic length ~2 sentences),
  `--ov-cream` text, `--ov-amber` used sparingly if any word needs emphasis
- Reuses the existing subtle noise-texture technique (`::after` with SVG
  turbulence filter) from the current `.philosophy` section for a bit of
  organic texture against the flat color

### 4. Showcase - "A Peek at the Games"

- Solid `--ov-navy-deep` background
- Small monospace label: `03 / A PEEK AT THE GAMES`
- Two to three screenshots (placeholder panels for now, real gameplay
  screenshots to be swapped in later) presented as framed "monitor windows":
  - Dark bezel (`--ov-navy-mid` background, `--ov-blue-mid` border,
    rounded corners)
  - Small chrome dots at the top of the frame (amber + blue) echoing
    browser/window chrome
  - Screenshot sits inside the frame; frame handles any color mismatch
    between the screenshot and the page background
  - Slight rotation (1-2deg, alternating) for an editorial, "pinned to a
    board" feel, consistent with the tilt treatment used on cards in the
    current landing page
  - Mobile: stacked vertically, full width
  - Desktop: 2-3 across, staggered vertical offset

### 5. Choose Your Path

- Solid `--ov-navy-mid` background
- Small monospace label: `04 / CHOOSE YOUR PATH`
- Three equally-weighted destination cards/panels, side by side on desktop,
  stacked on mobile, each with a distinct left/top accent border color
  (amber, blue-glow, mist) so they read as three distinct options rather
  than a ranked list:
  1. "Host a Live Game" -> `quiz:session_landing`
  2. "Browse the Gallery" -> `quiz:gallery`
  3. "View the Numbers" -> `quiz:analytics`
- This is the section where all three required links live together, framed
  as a deliberate choice rather than buried in nav/footer

### 6. Footer

- `--ov-ink` background, minimal
- Logo/wordmark, one-line tagline (placeholder), copyright line
- No repeated link columns - the three destinations already got a full
  section immediately above; footer stays quiet

## Interactions & Motion

- Reuse the existing scroll-reveal pattern (`IntersectionObserver` +
  `.visible` class + `opacity`/`transform` transition) already present in
  `landing.html`'s inline script, applied to the manifesto quote, showcase
  frames, and path cards
- Reuse the existing nav scroll-state toggle (`.nav.scrolled`)
- No new JS dependencies; vanilla JS consistent with the current file

## Responsive Behavior

- Mobile-first, since mobile is the primary access path for this app
- Single column throughout below the hero on all breakpoints (this page
  never had a good reason for multi-column below the fold in the new
  design except the showcase/path sections, which explicitly go
  side-by-side only at desktop widths)
- Hero copy block width and `background-position` adjusted at the existing
  `768px`/`1024px` breakpoints already used elsewhere in `landing.css`

## Testing

- No existing automated tests cover `quiz/landing.html`; none need updating
- Manual verification via `browser-verify` (or equivalent) at mobile and
  desktop widths: hero image loads and crops sensibly, all three required
  links present and pointing at the correct named URLs, auth-state
  conditionals render correctly for both authenticated and anonymous users,
  scroll-reveal and nav-scroll behavior work
- `black --check` still needs to pass (no Python changes expected, but the
  landing view itself is untouched, so this should be a non-issue)

## Open Items Deferred to Implementation

- Exact placeholder copy text (kept realistic-length, finalized later)
- Final gameplay screenshots (placeholder frames now, swapped in later
  without layout changes)
- Precise hero `background-position` values (tuned visually during
  implementation against real breakpoints, not fixed in this spec)
