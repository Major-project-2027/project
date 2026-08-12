# Cognivue Frontend — Architecture & Integration Guide

This document covers Parts 1, 13, and 14 of the brief: application architecture,
backend integration points, and a critical review of the current build.

---

## PART 1 — Application Architecture

### 1.1 Application flow

1. **Landing** (`/`) → unauthenticated marketing page → Login / Register.
2. **Auth** (`/login`, `/register`, `/forgot-password`) → on success, the app
   stores `{ user, token }` in Redux (`auth` slice) and routes to `/teacher`,
   `/student`, or `/admin` based on `user.role`.
3. **Role dashboard** → the hub for that role. From here, users reach every
   other feature: classes, attendance, tests, reports, notifications, settings.
4. **Live Classroom** (`/teacher/live/:classId`, `/student/live/:classId`) →
   entered from a "Join live" class card. This is a full-screen takeover
   (no sidebar) with its own header, video grid, AI monitoring / chat /
   participants side panel, and control bar.
5. **Online Test** → Teacher creates a test (`/teacher/tests`) → starts it
   (`/teacher/tests/:id/monitor`) while students join and answer
   (`/student/tests/:id/take`, with a timer that auto-submits) → both sides
   land on `/…/result`.

### 1.2 Navigation

Navigation is role-scoped and defined once in `src/constants/navigation.ts`
(`teacherNav`, `studentNav`, `adminNav`, `supportNav`). `AppShell` renders the
correct set based on a `role` prop passed down from each page — there is no
runtime role-detection logic scattered across components. Adding a nav item
to a role is a single-array edit and it appears in the desktop sidebar,
mobile drawer, and (implicitly) as an available route.

### 1.3 User journeys

- **Teacher**: sign in → dashboard (see today's classes + alerts) → start a
  live class → monitor students & respond to AI alerts → end class → review
  attendance/reports → create and proctor a test → export results.
- **Student**: sign in → dashboard (see schedule + pending tests) → join a
  live class → toggle camera/mic, raise hand, use chat → leave → check own
  attendance and notifications → take a scheduled test under a timer.
- **Admin**: sign in → platform-wide engagement/attendance overview → AI
  model health → drill into teacher/student rosters.

### 1.4 State management

Three layers, deliberately not overlapping:

| Concern | Tool | Why |
|---|---|---|
| Server/async data (classes, alerts, attendance, reports, tests, notifications) | **React Query** (`@tanstack/react-query`) | Caching, background refetch, loading/error states come for free; this is 90% of the app's data. |
| Global client state (auth session, sidebar collapsed, panel open) | **Redux Toolkit** (`src/store`) | Small, cross-cutting, needs to survive route changes; exactly what RTK is for. Kept intentionally minimal per the brief ("only if required"). |
| Local/ephemeral UI state (form inputs, modal open, selected video tile, timer) | **React `useState`/`useReducer`** | Scoped to one component tree; no reason to lift it. |
| Theme (dark/light) | **React Context** (`ThemeContext`) | Read by almost every component; Context avoids prop-drilling and persists to `localStorage`. |

### 1.5 Folder structure

```
src/
├── app/                  # (reserved) app-level composition/providers if the app grows past App.tsx
├── assets/               # icons, images
├── components/
│   ├── ui/               # design-system primitives: Button, Card, Badge, Input, Modal, Tabs, Switch, Avatar, Skeleton, EmptyState, ErrorState
│   ├── layout/            # AppShell, Sidebar, Topbar
│   ├── dashboard/         # StatCard, ClassCard
│   ├── charts/            # Recharts wrappers: EngagementTrendChart, BehaviorPieChart, AttendanceBarChart
│   ├── classroom/         # VideoTile, ParticipantsPanel, ChatPanel, ClassroomControls
│   ├── monitoring/        # ConfidenceRing, FocusPulse (signature motifs), AIMonitoringPanel
│   ├── notifications/     # (reserved for notification-specific widgets as they grow)
│   └── common/            # ProtectedRoute and other cross-cutting wrappers
├── constants/             # navigation.ts (role-based nav config)
├── context/                # ThemeContext
├── features/               # feature-scoped logic that isn't a "page" or generic "component"
│   ├── auth/                # zod schemas for login/register/forgot-password
│   ├── engagement/, classroom/, test/, reports/, notifications/   # reserved for feature-specific hooks/logic as they grow
├── hooks/                  # useAppStore (typed Redux hooks)
├── lib/                    # utils.ts — cn(), formatters, engagementTone()
├── mocks/                  # data.ts — deterministic mock data simulating backend responses
├── pages/
│   ├── auth/                # AuthLayout, LoginPage, RegisterPage, ForgotPasswordPage
│   ├── teacher/              # TeacherDashboardPage, AnalyticsPage
│   ├── student/              # StudentDashboardPage
│   ├── admin/                 # AdminDashboardPage
│   ├── shared/                 # pages reused across roles via a `role` prop: AttendancePage, ReportsPage, NotificationsPage, ProfilePage, SettingsPage, LandingPage, HelpPage, SupportPage, AboutPage
│   ├── live-classroom/          # TeacherLiveClassroomPage, StudentLiveClassroomPage
│   ├── test/                    # TeacherTestsPage, TeacherTestMonitorPage, StudentTestsPage, StudentTestTakingPage, ResultPage
│   └── error/                   # NotFoundPage
├── services/
│   ├── api/                 # client.ts (base fetch config, documented), endpoints.ts (typed per-domain functions)
│   └── websocket/            # (reserved) real-time engagement/alert streaming client
├── store/                   # Redux store + slices (auth, ui)
├── types/                   # domain.ts — the single source of truth for all data shapes
└── main.tsx, App.tsx, index.css
```

**Why pages are split into `teacher/`, `student/`, `shared/` rather than one
flat `pages/` folder:** several pages (Attendance, Reports, Notifications,
Profile, Settings) are *structurally identical* between roles but show
different data/actions. Building them once as `<Page role="teacher|student" />`
and mounting them from both route trees avoids duplicating markup while still
keeping teacher-only pages (Analytics, Test creation/monitoring) and
student-only pages (Test taking) physically separate and easy to find.

### 1.6 API integration strategy

See **Part 13** below for the full contract. In one sentence: every page
calls a function from `src/services/api/*`, never `fetch` directly and never
`src/mocks/*` directly — so swapping mock data for real HTTP calls is a
one-file change per domain with zero component edits.

### 1.7 Component hierarchy (representative — Teacher Dashboard)

```
TeacherDashboardPage
└── AppShell (role="teacher")
    ├── Sidebar (role-based nav)
    ├── Topbar (search, theme toggle, notifications, profile menu)
    └── main
        ├── StatCard × 4
        ├── Card > Tabs + ClassCard grid (classes)
        ├── Card > Alert list (AI alerts)
        ├── Card > EngagementTrendChart
        └── Card > BehaviorPieChart
```

```
TeacherLiveClassroomPage (full-screen, no AppShell)
├── header (live badge, class title, class-avg ConfidenceRing)
├── alert banner (dismissible)
├── video grid: VideoTile × N (each has its own ConfidenceRing + alert badge)
├── side panel (mutually exclusive): ParticipantsPanel | ChatPanel | AIMonitoringPanel
└── ClassroomControls (mic, camera, screen share, leave, panel toggles, timer)
```

---

## PART 13 — Frontend ↔ Backend API Integration Points

The frontend never talks to `fetch` directly from a component. Every data
need goes through `src/services/api/endpoints.ts`, grouped by domain. Today
each function resolves mock data after a simulated delay
(`simulateNetwork()` in `client.ts`); tomorrow, each function's body becomes
a real HTTP call — no component changes required.

| Domain | Function | Method & endpoint (future) | Used by |
|---|---|---|---|
| Auth | `authApi.login` | `POST /auth/login` | LoginPage |
| Auth | `authApi.register` | `POST /auth/register` | RegisterPage |
| Auth | `authApi.forgotPassword` | `POST /auth/forgot-password` | ForgotPasswordPage |
| Classes | `classesApi.list` | `GET /classes` | Teacher & Student dashboards, ClassCard grids |
| Classes | `classesApi.get` | `GET /classes/:id` | Live classroom header |
| Monitoring | `monitoringApi.liveStudents` | `GET /classes/:id/live-students`, then `WS /ws/classes/:id/engagement` for the live stream | TeacherLiveClassroomPage, VideoTile grid |
| Monitoring | `monitoringApi.alerts` | `GET /alerts?classId=` | Teacher dashboard alert center, AIMonitoringPanel |
| Attendance | `attendanceApi.list` | `GET /attendance?classId=&studentId=&date=` | AttendancePage (both roles) |
| Reports | `reportsApi.engagementTrend` | `GET /reports/engagement-trend?period=` | Dashboards, ReportsPage, AnalyticsPage |
| Reports | `reportsApi.behaviorBreakdown` | `GET /reports/behavior-breakdown?period=` | ReportsPage, AnalyticsPage |
| Notifications | `notificationsApi.list` | `GET /notifications`, `POST /notifications/:id/read` | NotificationsPage, Topbar bell |
| Tests | `testsApi.list` | `GET /tests`, `POST /tests`, `POST /tests/:id/submit` | Teacher/Student test pages |

**Real-time data**: `StudentLiveState` (engagement score, emotion, alerts)
updates every few seconds during a live session. The mock layer simulates
this with `refetchInterval` on the React Query hook; in production this
should be a WebSocket subscription (`WS_BASE_URL` is already defined in
`client.ts`) that pushes updates into the React Query cache via
`queryClient.setQueryData`, so components don't need to change from polling
to push — only the data-fetching hook does.

**Auth**: `client.ts` documents (as a comment, not live code) the exact
`fetch` wrapper to activate — attaching a bearer token from `localStorage`
and throwing a typed `ApiError` on non-2xx responses.

---

## PART 14 — Review: Weaknesses & Suggested Improvements

### Known weaknesses in the current build

- **All data is mocked.** Every screen renders real, varied data, but none
  of it is live — this was explicit in the brief since no backend exists yet.
- **No WebSocket implementation**, only polling via `refetchInterval`. Fine
  for a prototype; will feel laggy under real classroom load.
- **No authentication enforcement.** `ProtectedRoute` currently allows
  browsing without signing in (by design, so reviewers can explore every
  screen) — the redirect is commented, not deleted, and should be re-enabled
  before any real deployment.
- **No automated tests.** No unit tests (Vitest) or E2E tests (Playwright)
  exist yet for a codebase of this size.
- **Single large `EngagementTrendChart` chunk** (~330KB before gzip) because
  Recharts pulls in D3 internally; this is the single biggest thing to
  address before a production launch.
- **Video tiles are illustrative**, not wired to WebRTC — there's no actual
  camera/mic stream, screen share, or peer connection yet.

### Enterprise-level UI improvements

- Introduce a proper design-token file consumed by both web and a future
  mobile app (React Native), rather than tokens living only in Tailwind CSS.
- Add virtualization (e.g. `react-virtual`) to the video grid and student
  lists once class sizes exceed ~40, to keep the DOM light.
- Replace ad-hoc `useState` panel toggles in the classroom with a small
  state machine (XState) — join/monitor/test-taking flows have enough
  states (joining → verifying face → connected → alert-active → leaving)
  that implicit boolean flags will become error-prone as features grow.

### UX improvements

- Add an explicit "device check" step (camera/mic/face preview) before
  joining a live class, matching Zoom/Meet conventions, instead of joining
  directly into the session.
- Surface *why* an alert fired (e.g. a small confidence/reasoning tooltip)
  directly on the AIMonitoringPanel metric rows, not just in the alert list.
- Add undo/confirmation on more destructive actions (ending a test, deleting
  a class) — currently only test submission has a confirm step.

### Accessibility improvements

- Full keyboard navigation audit for the live classroom control bar and
  video grid (currently mouse/touch-first).
- `aria-live` regions for real-time alert banners so screen readers announce
  new AI alerts without the user needing to notice a visual change.
- Color is not the only signal for engagement tone (icons/labels are already
  paired with color in most places), but the video-tile ring colors should
  gain a text-equivalent for colorblind users.
- Respect `prefers-reduced-motion` more thoroughly — currently only handled
  globally in CSS; Framer Motion transitions should also check this at the
  component level for users who need it disabled entirely rather than sped up.

### Scalability improvements

- Move from `refetchInterval` polling to WebSocket push for all "live"
  queries (engagement, alerts) once the realtime service exists.
- Split `mocks/data.ts` generators behind the same interface as
  `services/api`, but namespaced per feature, so mock volume can grow
  (e.g. 500 students) without one file becoming unwieldy.
- Add route-level error boundaries (currently only per-query `ErrorState`
  components) so a single failing widget can't blank a whole page.
- Introduce feature flags (e.g. via a simple `useFeatureFlag` hook backed by
  a `/config` endpoint) so admin/teacher/student capabilities can be toggled
  per institution without redeploying the frontend.

---

## Running the project

```bash
npm install
npm run dev       # start dev server (Vite)
npm run build     # type-check + production build
npm run preview   # preview the production build
```

Environment variables (optional, see `src/services/api/client.ts`):

```
VITE_API_BASE_URL=https://api.cognivue.app/v1
VITE_WS_BASE_URL=wss://realtime.cognivue.app
```
