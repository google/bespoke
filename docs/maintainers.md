# Bespoke Developer Manual

## Contributing & Python Development

Before submitting changes to the Python codebase, run the formatters, linters, tests, and type checks:

```sh
uv run ruff format
uv run ruff check
uv run -m unittest -b
uv run --with=mypy mypy .
```

## Maintainer Tools & Scripts

The `maintainers/` directory contains CLI scripts to help with common tasks:

### 1. Package Cards into SQLite Dataset (`maintainers/package_cards.py`)

Bundles all card data, audio files, translations and vocabulary into a SQLite
`.db` dataset package. Usable by both the Python and Android learning app.

```sh
uv run -m maintainers.package_cards --target="Japanese" --native="English"
```

### 2. Verify Packaged Dataset (`maintainers/verify_package.py`)

Validates a given `.db` file has the correct format.

```sh
uv run -m maintainers.verify_package cards/japanese_(english).db
```

### 3. Card creation statistics (`maintainers/card_distribution.py`)

After you generate JSON files for a new deck, this script shows statistics about
card coverage per vocabulary unit, untagged units, and translation:

```sh
uv run -m maintainers.card_distribution --target="Japanese" --native="English"
```

### 4. Inspect Deck Urgency (`maintainers/deck_scores.py`)

Displays spaced-repetition deck stats, next task urgency, and card score
rankings for the next unit. Useful for debugging while learning:

```sh
uv run -m maintainers.deck_scores --target="Japanese"
# Or inspect a specific vocabulary unit:
uv run -m maintainers.deck_scores --target="Japanese" --unit="食べる"
```

### 5. Manual Sentence Tagging Inspection (`maintainers/sentence_quality.py`)

Generates and tags example sentences for inspection:

```sh
uv run -m maintainers.sentence_quality --target="Japanese" --difficulty=B1 --cards_per_call=8
```

### 6. Translate Vocabulary Units (`maintainers/translate_units.py`)

Generates LLM translations for target vocabulary units into the native language:

```sh
uv run -m maintainers.translate_units --target="Japanese" --native="English"
```

### 7. Filter Cards by Sentence (`maintainers/index_filter.py`)

Removes specific sentences from the card index according to a text file list:

```sh
uv run -m maintainers.index_filter --target="Japanese" --native="English" --sentences=bad_sentences.txt
```

### 8. Convert Dataset to New Native Language (`maintainers/convert_dataset.py`)

Converts an existing `.db` dataset package to a new native language by
translating vocabulary units, generating native sentence translations via LLM,
and synthesizing native audio clips:

```sh
uv run -m maintainers.convert_dataset --target="Japanese" --from-native="English" --to-native="German"
```

### 9. Replace Dataset Translations (`maintainers/replace_translation.py`)

Overwrites translations in a `.db` dataset package in-place:

```sh
# Replace a single unit translation:
uv run -m maintainers.replace_translation --db=cards/japanese_(english).db --unit-id="大学生" --translation="college student"

# Or apply bulk replacements from a CSV file (with header unit_id,translation):
uv run -m maintainers.replace_translation --db=cards/japanese_(english).db --file=fixes.csv
```

### 10. Transition Deck State (`maintainers/transition_deck.py`)

Only necessary if you started learning on a commit from May 2026 or earlier.
Migrates legacy deck rating states to updated DictionaryUnit IDs:

```sh
uv run -m maintainers.transition_deck --target="Japanese"
```

## Android App Development and Testing

The native Android application is located in the `android/` directory.

### Prerequisites

- JDK 21 (e.g. `export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`).
- Android SDK (compileSdk 34, minSdk 26).

### Building and Testing

Navigate to the `android/` directory to run Gradle commands:

For tests and checks, use the following:

```sh
./gradlew test
./gradlew lint
./gradlew check
```

To build an APK for the app in debug mode, run:

```sh
./gradlew assembleDebug
```

For release mode, instead create APK and App Bundle (AAB) with:

```sh
./gradlew assembleRelease
./gradlew bundleRelease
```
