# Bespoke Developer Manual

## Contributing & Python Development

To add a new language, see instructions at the top of `bespoke/languages.py`.

Before submitting changes to the Python codebase, run the formatters, linters, tests, and type checks:

```
uv run ruff format
uv run ruff check
uv run -m unittest
uv run --with=mypy mypy .
```

## Maintainer Tools & Scripts

The `maintainers/` directory contains CLI scripts to help with common tasks:

### 1. Package Cards into SQLite Dataset (`maintainers/package_cards.py`)

Bundles all card data, audio files, translations, vocabulary into an SQLite
`.db` dataset package. Usable by both the Python and Android learning app.

```
uv run -m maintainers.package_cards --target=japanese --native=english
```

### 2. Verify Packaged Dataset (`maintainers/verify_package.py`)

Validates a given `.db` file has the correct format.

```
uv run -m maintainers.verify_package cards/japanese.db
```

### 3. Card creation statistics (`maintainers/card_distribution.py`)

After you generate JSON files for a new deck, this script shows statistics about
card coverage per vocabulary unit, untagged units, and translation:

```
uv run -m maintainers.card_distribution --target=japanese --native=english
```

### 4. Inspect Deck Urgency (`maintainers/deck_scores.py`)

Displays spaced-repetition deck stats, next task urgency, and card score
rankings for the next unit. Useful for debugging while learning:

```
uv run -m maintainers.deck_scores --target=japanese
# Or inspect a specific vocabulary unit:
uv run -m maintainers.deck_scores --target=japanese --unit="食べる"
```

### 5. Manual Sentence Tagging Inspection (`maintainers/sentence_quality.py`)

Generates and tags examples sentences generation:

```
uv run -m maintainers.sentence_quality --target=japanese --difficulty=B1 --count=8
```

### 6. Translate Vocabulary Units (`maintainers/translate_units.py`)

Generates LLM translations for target vocabulary units into the native language:

```
uv run -m maintainers.translate_units --target=japanese --native=english
```

### 7. Filter Cards by Sentence (`maintainers/index_filter.py`)

Removes specific sentences from the card index according to a text file list:

```
uv run -m maintainers.index_filter --target=japanese --native=english --sentences=bad_sentences.txt
```

### 8. Transition Deck State (`maintainers/transition_deck.py`)

Only necessary if you started learning on a commit from May 2026 or earlier.
Migrates legacy deck rating states to updated DictionaryUnit IDs:

```
uv run -m maintainers.transition_deck --target=japanese
```

## Android App Development and Testing

The native Android application is located in the `android/` directory.

### Prerequisites

- JDK 21 (e.g. `export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`).
- Android SDK (compileSdk 34, minSdk 26).

### Building and Testing

Navigate to the `android/` directory to run Gradle commands:

For tests and checks, use the following:

```
./gradlew test
./gradlew lint
./gradlew check
```

To build an APK for the app in debug mode, run:

```
./gradlew assembleDebug
```

For release mode, instead create APK and App Bundle (AAB) with:

```
./gradlew assembleRelease
./gradlew bundleRelease
```
