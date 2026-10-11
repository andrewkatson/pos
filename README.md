# Good Vibes Only (formerly Positive Only Social)
[![Android Tests](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml)
[![iOS Tests](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml)
[![Backend Tests](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml)
[![Website Tests](https://github.com/andrewkatson/pos/actions/workflows/website-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/website-tests.yml)

Good Vibes Only is a social network that only allows positive or neutral text
and image posts. Every post, comment, username, bio and profile photo is checked
by automated moderation before anyone else can see it, so the feed stays a
place people come to feel better. It runs at
[smiling.social](https://smiling.social), with native iOS and Android apps.

## Content guidelines

1. No swear words
2. No nudity
3. No sexually suggestive content
4. No gore
5. No hate speech
6. No harassment
7. No bullying
8. No misinformation

Neutral content is allowed. Content that starts sad but ends on a happy or
hopeful note is also allowed. These will be updated as time goes on.

## Repository layout

| Directory | What it is |
| --- | --- |
| [`backend/`](backend/) | Django API; `user_system` is the main app |
| [`website/`](website/) | React + TypeScript SPA built with Vite |
| [`ios/`](ios/) | iOS app (Xcode project "Positive Only Social") |
| [`android/`](android/) | Android app |
| [`docs/`](docs/) | Product spec and operations docs |

## Documentation

Detailed behavior — moderation, visibility, sharing, accounts, images,
deployment and more — lives in [`docs/`](docs/README.md).
