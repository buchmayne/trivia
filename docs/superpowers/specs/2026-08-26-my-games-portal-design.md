# My Games Portal & Host Recovery — Design

## Problem

A host running a live `GameSession` has no way to recover control if their browser
tab, connection, or `localStorage` is lost mid-game. Host authorization is entirely
client-side: `GameSession.admin_token` is generated once at session creation and
stored in `localStorage` (`session_${code}_admin`). If that value is lost, the host
has no path back into the session — even though `GameSession.host_user` already
records who created it. The result: the session is orphaned, teams can't progress,
and all answers/progress up to that point are effectively wasted, because there is
no way to end, resume, or review the game.

This design adds:

1. A **"My Games" portal** — a logged-in host's list of every session they've
   hosted, showing status and letting them resume or review it.
2. A **reclaim mechanism** — a way for the verified owner (`host_user`) of a
   session to get a fresh `admin_token` and regain host control, without relying on
   anything stored in the original browser.

Out of scope: recovery for anonymous hosts (sessions with `host_user = null`,
created while hosting example games while logged out) — this is an accepted gap
consistent with the rest of the app's permission model (anonymous hosting is only
allowed for example games in the first place).

## Data model changes

**None.** This design reuses existing fields:

- `GameSession.host_user` — already set at session creation for logged-in hosts.
  Used to scope the portal list (`host_user=request.user`) and to authorize reclaim.
- `GameSession.admin_token` — rotated (regenerated) on reclaim; no schema change.
- `SessionTeam.last_seen` — already updated on every team poll (~every 2s while a
  team's browser is active). Used to compute "currently active" presence at query
  time; not stored as a derived field.

No migration is required.

## What counts as "active"

There is no new stored status. "Active" is a display-time computation, not a
database state:

- A session is **resumable** if its `status != COMPLETED`. All resumable sessions
  appear in the portal's active section, regardless of how long ago they were
  touched — because teams can rejoin later (`allow_late_joins`), the host should
  always be able to get back into a non-completed session.
- Within that set, a session is flagged **"currently active"** if at least one of
  its teams has `last_seen` within the last 60 seconds. This is purely informational
  (a badge like "3 teams active now" vs "no one currently connected" vs "paused 2
  hours ago"), used to help the host triage which sessions need attention — it does
  not gate the rejoin action.
- Sessions with `status == COMPLETED` are shown separately as read-only history.

No background job, periodic task, or new "abandoned" status is introduced in this
design. If in practice hosts accumulate large numbers of long-dead resumable
sessions, that can be revisited later (e.g. auto-completing sessions inactive past
some threshold) — not needed for v1.

## Reclaim endpoint

`POST /api/sessions/<code>/reclaim/`

- **Auth:** requires a normal authenticated Django session (login cookie + CSRF
  protection — this is not a public/anonymous endpoint like `create_session`, so it
  is *not* `@csrf_exempt`).
- **Authorization:** the endpoint loads the `GameSession` by `code` and checks
  `session.host_user == request.user`.
  - If the session doesn't exist: `404`.
  - If `request.user` is not the owner (including when `host_user is null`):
    `403`, generic "not authorized" message. The response does not distinguish
    "session exists but isn't yours" from "session doesn't exist," to avoid leaking
    which codes are valid.
- **Completed sessions:** reclaim is still permitted for completed sessions (it's
  harmless — regains read access), though the portal routes completed games to
  "View Results" rather than "Rejoin as Host," so this path is primarily exercised
  for non-completed sessions.
- **On success:** generate a new `admin_token` (`secrets.token_urlsafe()`), save it
  to the session, and return `{ "code": ..., "admin_token": ... }`. This immediately
  invalidates the previous token.
- **Rate limiting:** apply the same IP-based rate limiting pattern used elsewhere in
  `session_api.py` (e.g. `create_session`'s `@ratelimit`) to prevent abuse.

### Frontend flow

The "Rejoin as Host" button in the portal calls this endpoint, then:

1. Stores the returned `admin_token` in `localStorage` under the same
   `session_${code}_admin` key that `play.html` already reads.
2. Navigates to `/play/<code>/`.

From there, `play.html`'s existing admin bootstrap logic (validate token → render
admin view) works unchanged — no changes needed to the live session page's core
flow.

### Stale-tab handling

Because reclaiming rotates the token, any other tab/device still holding the old
token will get `403 Invalid admin token` on its next poll (every 2s, via
`require_admin_token`). Today this would surface as a generic/opaque error. This
design adds a specific handler in `play.html`'s polling error path: on a `403` for
an admin request, show "This session is now being controlled from another device"
instead of a generic failure, and stop polling (rather than retrying in a loop).

## Portal page

`GET /play/mine/` — a new top-level nav item, **"My Games,"** visible in `base.html`
only when `request.user.is_authenticated`.

- **Query:** `GameSession.objects.filter(host_user=request.user).select_related("game").prefetch_related("teams")`.
- **Ordering:**
  - Non-completed sessions first, ordered by most recent team activity (most
    recently active first).
  - Completed sessions after, ordered by `completed_at` (falling back to
    `created_at`) descending.
- **Pagination:** 20 per page — but only applied within the completed/history
  section. All non-completed (resumable) sessions are always shown above the fold,
  unpaginated, so an old active/paused game is never buried on page 2 behind a long
  completed-game history.
- **Per-row data:** game name, session code, status, team count, presence badge
  ("N teams active now" / "no one currently connected" / "paused Xh ago"), round or
  progress indicator (current round / total rounds), created date, and — for
  completed sessions — completion date.
- **Actions:**
  - Non-completed: **Rejoin as Host** → calls reclaim, then redirects as described
    above.
  - Completed: **View Results** → links directly to `/play/<code>/`, which already
    renders a read-only leaderboard/completed view (via the existing public
    `get_leaderboard_data` endpoint — no new results view needs to be built).

## Error handling / edge cases

- Anonymous-hosted sessions (`host_user is null`) never appear in any user's
  portal and cannot be reclaimed by anyone. This is an accepted limitation
  consistent with anonymous hosting already being restricted to example games.
- A session with zero teams ever joined (host disconnected before anyone played)
  still appears in the active list, since its status is not `COMPLETED` — shown
  with "no one currently connected."
- Reclaiming a session you don't own returns `403` regardless of whether the
  session exists, to avoid leaking valid codes.
- Reclaiming rotates the token, so concurrent multi-tab/device host control is not
  supported — only the most recent reclaim wins. This is judged acceptable: it
  matches the existing single-active-admin assumption in `admin_last_seen`/pause
  logic, and gives a clear resolution instead of silent conflict.

## Testing

- **API tests** (`quiz/tests/test_session_api.py` or similar):
  - Reclaim succeeds for the owning authenticated user; token rotates; old token
    is rejected afterward.
  - Reclaim returns `403` for a non-owning authenticated user.
  - Reclaim returns `403` for an anonymous request.
  - Reclaim returns `404` for a nonexistent code.
  - Reclaim succeeds on a `COMPLETED` session.
- **View tests** (`quiz/tests/test_session_views.py`):
  - Portal only lists sessions where `host_user == request.user`.
  - Pagination applies only to the completed section; active sessions are never
    paginated out.
  - Presence badge reflects `SessionTeam.last_seen` recency correctly.
  - Portal route requires login (redirects/403s for anonymous users).
- **E2E** (Playwright, new `e2e/tests/my-games.spec.ts` or extending
  `host-flow.spec.ts`):
  - Host a game, add a team, simulate losing the host tab (clear `localStorage`),
    visit the portal, click "Rejoin as Host," confirm host controls work and the
    team's existing answers/progress are intact.
  - Confirm a stale tab with the old token surfaces the "controlled from another
    device" message rather than a generic error.
