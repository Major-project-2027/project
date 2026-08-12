# Cognivue — AI Classroom Engagement Platform (Frontend)

Production frontend for the **Predictive Multimodal Student Engagement and
Cognitive Monitoring System** final-year engineering project. This repo is
the complete UI layer — teacher/student/admin dashboards, live classroom,
AI monitoring panel, online testing, reports, and notifications — built to
integrate with the already-trained AI models (face auth, emotion detection,
gaze/head pose, object detection, voice analysis, LSTM engagement prediction)
once the backend exists.

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full architecture,
API integration contract, and a critical review of the current build.

## Stack

React 19 · TypeScript · Vite · Tailwind CSS v4 · React Router · React Query ·
Redux Toolkit · Framer Motion · React Hook Form + Zod · Recharts · Lucide Icons

## Quick start

```bash
npm install
npm run dev
```

Open http://localhost:5173. Sign in with any email containing "teacher" or
"student" (e.g. `teacher@bit.edu` / `student@bit.edu`) and any password —
auth is mocked until a backend is connected.

## Scripts

- `npm run dev` — start the dev server
- `npm run build` — type-check and build for production
- `npm run preview` — preview the production build locally
- `npm run lint` — lint the codebase

## Project status

All UI is fully built and interactive against realistic mock data
(`src/mocks/data.ts`). No backend, database, or AI inference code is
included in this repo — see ARCHITECTURE.md Part 13 for exactly how each
screen will connect to real APIs.
