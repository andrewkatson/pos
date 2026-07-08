# CLAUDE.md

## Repo layout

- `backend/` — Django API; `user_system` is the main app.
- `website/` — React 19 + TypeScript SPA built with Vite (Node 22).
- `ios/` — Xcode project ("Positive Only Social").
- `android/` — Android app.

## Workflow

- Every PR must be opened against the `dev` branch, and work must be done in a worktree (not directly on a checkout of a shared branch).
- The root `README.md` is the product spec — it documents domain behavior in detail (content guidelines, banning/shadow-ban semantics, S3 image cleanup, new-device login emails). Consult it before changing domain logic, and update it when behavior changes.
- Backend model changes need a Django migration in `backend/user_system/migrations/`.

## Building and testing

- See the workflows in `.github/workflows/` for how the project is built and tested. Relevant files: `website-tests.yml`, `backend-tests.yml`, `ios-tests.yml`, `android-tests.yml`, and `codeql.yml`.
- Backend (Python 3.14, from `backend/`): run both `python -m pytest tests` and `python manage.py test user_system.tests` before finishing backend work.
- Website (from `website/`): CI runs `npm run lint`, `npx tsc -b --noEmit`, `npm test`, and `npm run build` — run all four before finishing website work.
- CI is path-filtered: only workflows matching the touched directories run, so a change spanning multiple subprojects needs each affected suite run locally.

## Product invariants

- This is a positivity-only social network — content moderation (classifiers, visibility, bans) is core domain logic, not an add-on. Changes to `backend/user_system/classifiers/`, `visibility.py`, or ban logic deserve extra test coverage.
