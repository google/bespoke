# Bespoke Android

Bespoke Android is an offline-first Android application for language learning.

## Overview

The app allows learners to practice vocabulary and sentences across different
learning modes (Listen, Speak, Read, and Write):

- **Self-Contained Datasets**: Reads pre-packaged SQLite `.db` dataset files
  containing card definitions, embedded OGG audio, vocabulary, translations,
  and indexes.
- **Spaced Repetition Engine**: Calculates urgency scores and review intervals
  based on rating history and user responses.
- **Interactive Review UI**: Built with Kotlin and Jetpack Compose, featuring
  front/back card views, phonetic guides, embedded audio playback (normal,
  slow, and native speeds), and word-level color-cycling ratings.
- **Dark & Light Mode**: Supports both light and dark themes and persists user
  preferences and deck selection across sessions.

> [!NOTE]
> This application is strictly for **learning and reviewing cards**, not for
> creating or building them. Card creation, sentence generation, audio
> synthesis, and dataset packaging are handled by the Python tooling in the
> repository root.

## Running Tests

To run the Android unit and Compose tests:

```bash
cd android
./gradlew testDebugUnitTest
```

Or to run all test tasks:

```bash
cd android
./gradlew test
```

## AI Authorship

The entire Bespoke Android application was coded by AI.
