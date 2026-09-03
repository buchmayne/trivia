# Implementation Plan: My Games Portal & Host Recovery

Spec: `docs/superpowers/specs/2026-08-26-my-games-portal-design.md`

## Shared context for all tasks

- App: Django project `pub_trivia`, live-session logic lives in `quiz/session_api.py`
  (JSON API, token-based auth), `quiz/session_views.py` (HTML views), `quiz/models.py`
  (`GameSession`, `SessionTeam`), `quiz/urls.py` (routes).
- Host auth today: `GameSession.admin_token` is a bearer token stored client-side in
  `localStorage` (`session_${code}_admin`) and checked by the `require_admin_token`
  decorator in `quiz/session_api.py`. `GameSession.host_user` already records the
  owning Django user for logged-in hosts but is currently unused for re-auth.
- No data model changes are needed anywhere in this plan — every task reuses
  existing fields (`host_user`, `admin_token`, `SessionTeam.last_seen`).
- There is no single shared site-wide nav partial. `quiz/templates/quiz/landing.html`
  has a top nav (`.nav-auth`) shown on the main site home page, and
  `quiz/templates/quiz/sessions/landing.html` has its own button row
  (`.landing-buttons`) for the `/play/` entry point. Both need updating for
  discoverability — see Task 4.
- Backend tests live in `quiz/tests/` (pytest/Django test runner — check
  `quiz/tests/README.md` for conventions). E2E tests live in `e2e/tests/`
  (Playwright) with fixtures in `e2e/fixtures/session.ts` and helpers in
  `e2e/helpers/session-helpers.ts`.

---

## Task 1: Reclaim endpoint

**Goal:** Let the authenticated, verified owner of a `GameSession` regain host
control by issuing a fresh `admin_token`, without needing anything from the
original browser.

**Context:** This is the core fix for the reported bug — today, losing
`admin_token` locks the host out of their own session permanently, even though
`host_user` already identifies them.

**Relevant files:**
- `quiz/session_api.py` — add `reclaim_session(request, code)`, alongside the
  existing `create_session` and `rejoin_session` (team-side equivalent, for
  reference on patterns/response shape).
- `quiz/urls.py` — add `path("api/sessions/<str:code>/reclaim/", session_api.reclaim_session, name="session_reclaim")`.
- `quiz/tests/test_session_api.py` — new tests.

**Proposed approach:**
- `POST /api/sessions/<code>/reclaim/`, **not** `@csrf_exempt` (unlike the public
  endpoints) — this requires a real logged-in Django session, so normal CSRF
  protection applies.
- Manually check `request.user.is_authenticated` (don't use `@login_required`,
  which redirects — this is a JSON API and should return `403` instead).
- `session = get_object_or_404(GameSession, code=code)` → `404` if missing.
- If `not request.user.is_authenticated or session.host_user != request.user`:
  return a generic `403` ("not authorized") — same response whether the session
  doesn't exist for this user or exists but isn't theirs, to avoid leaking valid
  codes to non-owners. (The `404` for a truly nonexistent code is fine to keep
  distinct, per the spec.)
- On success: `session.admin_token = secrets.token_urlsafe()`; `session.save()`;
  return `{"code": session.code, "admin_token": session.admin_token}`.
- Allowed on `COMPLETED` sessions too (no status check needed) — reclaiming is
  harmless there, it just regains read access.
- Apply `@ratelimit(key="ip", rate="10/m", method="POST", block=True)`, matching
  the pattern already used on `create_session`.

**Acceptance criteria:**
- Owner (authenticated user matching `host_user`) reclaiming gets a new
  `admin_token`, and the previous token is rejected by `require_admin_token`
  afterward (`403 Invalid admin token`).
- Authenticated non-owner gets `403`.
- Anonymous request gets `403` (not a redirect).
- Nonexistent code gets `404`.
- Reclaiming a `COMPLETED` session succeeds.

**Source reference:** Design doc, "Reclaim endpoint" section.

**Verify:**
```
python manage.py test quiz.tests.test_session_api -v 2
```
(or the project's configured pytest command — check `quiz/tests/README.md`)

---

## Task 2: Stale-tab handling in the live session page

**Goal:** When an admin's polling request gets rejected because their token was
rotated out from under them (someone else reclaimed the session), show a clear,
specific message instead of a generic/opaque error, and stop polling.

**Context:** Task 1 rotates `admin_token` on reclaim, which means any other open
tab/device with the old token starts failing its next poll. Today's generic error
handling would be confusing here — this task makes that specific failure mode
legible.

**Relevant files:**
- `quiz/templates/quiz/sessions/play.html` — `pollState()` function (~line 405)
  and surrounding admin-role error handling.

**Proposed approach:**
- In the admin poll's error handling, detect a `403` response specifically for
  admin-role requests (as opposed to team-role, which has its own token/flow).
- On that `403`: stop the poll timer (`clearInterval(pollTimer)`), and render a
  message such as "This session is now being controlled from another device."
  instead of continuing to retry or showing a generic failure.
- Do not change team-side polling/error handling — this task is scoped to the
  admin path only.

**Acceptance criteria:**
- An admin tab whose token has been invalidated (via reclaim elsewhere) shows the
  "controlled from another device" message within one poll interval (~2s) and
  stops polling.
- Team polling and normal admin operation are unaffected.

**Source reference:** Design doc, "Stale-tab handling" section.

**Verify:** Manual check (open two tabs as admin, reclaim from a third, confirm
message appears in the stale tab) plus the E2E scenario in Task 5.

---

## Task 3: "My Games" portal view

**Goal:** Build the `/play/mine/` page listing every session the logged-in user
has hosted, with status, presence, and pagination per the spec.

**Context:** This is the primary UI surface for the whole feature — the list a
host lands on to find and recover (or review) their sessions.

**Relevant files:**
- `quiz/session_views.py` — add `my_games(request)`.
- `quiz/urls.py` — add `path("play/mine/", session_views.my_games, name="session_my_games")`.
- New template: `quiz/templates/quiz/sessions/my_games.html`.
- `quiz/tests/test_session_views.py` — new tests.

**Proposed approach:**
- Require login (standard `@login_required` is fine here — this is an HTML page,
  redirect-to-login is the expected UX).
- Query:
  `GameSession.objects.filter(host_user=request.user).select_related("game").prefetch_related("teams")`.
- Split into two querysets in Python (or two DB queries): non-completed
  (`status != COMPLETED`) and completed (`status == COMPLETED`).
- Non-completed: no pagination, ordered by most-recent team activity (compute
  `max(team.last_seen for team in session.teams.all())` per session, or annotate
  with `Max("teams__last_seen")`; sessions with no teams sort by `created_at`).
- Completed: paginate with Django's `Paginator`, 20 per page, ordered by
  `completed_at` descending (fall back to `created_at` if `completed_at` is null).
- For each session, compute a presence badge in the view or template: teams with
  `last_seen` within the last 60 seconds → "N teams active now"; else if any teams
  exist → "no one currently connected"; else "no teams have joined yet". For
  paused/other non-completed statuses, also show how long ago the session was last
  touched (e.g. "paused 2h ago", based on most recent `admin_last_seen`/team
  `last_seen`).
- Template renders two sections: "Active Games" (unpaginated) and "Game History"
  (paginated), each row showing game name, code, status, team count, presence
  badge, round/progress, and dates.
- Row actions are wired in Task 4 (this task can render disabled/placeholder
  buttons or the final markup, but the JS behavior belongs to Task 4).

**Acceptance criteria:**
- Only sessions where `host_user == request.user` appear; other users' sessions
  never leak into the list.
- Anonymous requests are redirected to login.
- All non-completed sessions appear regardless of page (never paginated out).
- Completed sessions paginate correctly at 20/page.
- Presence badges reflect actual `SessionTeam.last_seen` data (verify with teams
  seen recently vs. teams stale for hours).

**Source reference:** Design doc, "What counts as 'active'" and "Portal page"
sections.

**Verify:**
```
python manage.py test quiz.tests.test_session_views -v 2
```

---

## Task 4: Wire up portal actions and add navigation entry points

**Goal:** Make "Rejoin as Host" and "View Results" actually work from the portal,
and make the portal discoverable from the existing entry points into the app.

**Context:** Task 3 renders the list; this task connects it to Task 1's reclaim
endpoint and adds links so logged-in users can actually find `/play/mine/`.

**Relevant files:**
- `quiz/templates/quiz/sessions/my_games.html` — button behavior (JS).
- `quiz/templates/quiz/landing.html` — `.nav-auth` block (add a "My Games" link
  when `user.is_authenticated`).
- `quiz/templates/quiz/sessions/landing.html` — `.landing-buttons` row (add a
  third button/link to `/play/mine/`, shown only when authenticated — this
  template currently renders the same for everyone, so check `request.user` in
  `session_views.session_landing` and pass an `is_authenticated` context flag, or
  use `{% if user.is_authenticated %}` directly since Django's auth context
  processor is presumably enabled — confirm via `pub_trivia/settings.py`
  `TEMPLATES` config).

**Proposed approach:**
- "Rejoin as Host" button: `POST` to `/api/sessions/<code>/reclaim/` (include
  Django's CSRF token — this is a same-origin authenticated request, use the
  standard `{% csrf_token %}` / `X-CSRFToken` header pattern already used
  elsewhere in the codebase for non-exempt POSTs), then on success store
  `admin_token` into `localStorage.setItem('session_${code}_admin', token)` and
  `localStorage.setItem('session_${code}_role', 'admin')`, then
  `window.location.href = '/play/' + code + '/'`.
- "View Results" button/link: plain `<a href="/play/{{ code }}/">` — no API call
  needed, `play.html` already renders completed/leaderboard state for
  `COMPLETED` sessions.
- Add "My Games" link to both existing entry points described above, gated on
  authentication, pointing at `{% url 'quiz:session_my_games' %}`.

**Acceptance criteria:**
- Clicking "Rejoin as Host" on a non-completed session lands the user in
  `play.html` with full host controls, matching what they'd see if they'd never
  lost the original tab.
- Clicking "View Results" on a completed session lands in the read-only
  leaderboard view.
- "My Games" link is visible on the main landing page and the `/play/` landing
  page when logged in, and absent (or not rendered) when logged out.

**Source reference:** Design doc, "Frontend flow" and "Portal page" sections.

**Verify:** Manual click-through, plus covered by the E2E test in Task 5.

---

## Task 5: End-to-end recovery test

**Goal:** Prove the full failure/recovery loop works: a host loses their tab
mid-game and can get back in via the portal without losing any team progress.

**Context:** This is the scenario from the original bug report — it needs a real
browser-level test, not just unit tests of the individual pieces.

**Relevant files:**
- New `e2e/tests/my-games.spec.ts`.
- `e2e/fixtures/session.ts` — the existing `createSession` fixture creates
  sessions anonymously (unauthenticated), which won't have `host_user` set. This
  test needs an authenticated host, so it will likely need either a new fixture
  or a helper that logs in a test Django user (via the app's login form or a
  Playwright `storageState`) before calling `createSession`-equivalent logic.
  Check `e2e/tests/qa-*.spec.ts` and Django test fixtures (e.g.
  `quiz/tests/test_auth.py`) for how test users are provisioned elsewhere in the
  suite.
- `e2e/helpers/session-helpers.ts` — reuse `waitForAdminView`, `adminStartGame`,
  etc.

**Proposed approach:**
1. Log in as a test host user (create the user via Django fixture/management
   command if the suite doesn't already have one available for E2E).
2. Host a session, add at least one team, submit an answer as that team.
3. Simulate losing the host tab: clear `localStorage` (or open a fresh browser
   context with no storage) instead of using the original admin page.
4. Visit `/play/mine/`, confirm the session appears as active/resumable with the
   correct team count.
5. Click "Rejoin as Host", confirm the admin view loads and reflects the team's
   existing answer/progress (nothing was lost).
6. Separately: with two open host contexts (old + reclaimed), confirm the old one
   surfaces "controlled from another device" per Task 2 rather than a silent or
   generic failure.

**Acceptance criteria:**
- Full recovery flow passes: host recovers control, team progress is intact,
  game can continue and be completed normally.
- Stale-tab messaging is verified.

**Source reference:** Design doc, "Testing" section.

**Verify:**
```
npx playwright test e2e/tests/my-games.spec.ts
```

---

## Suggested order

1. Task 1 (reclaim endpoint) — foundational, independently testable.
2. Task 3 (portal view) — can be built in parallel with Task 1; only needs read
   access to existing models.
3. Task 2 (stale-tab handling) — small, depends conceptually on Task 1's token
   rotation but is independently implementable/testable.
4. Task 4 (wire-up + nav) — depends on Task 1 and Task 3 both existing.
5. Task 5 (E2E) — last, exercises everything together.
