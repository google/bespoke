# Bespoke Card Creation

If you don't find existing cards, you can follow this manual to create your own.
The example commands generate cards to let English speakers learn Japanese.
If the language you speak or want to learn does not exist yet, you can find
instructions in [languages.py](../bespoke/languages.py) to add them, both as a
target for learning and your native language.

## Setup

The commands below run Bespoke with
[uv](https://docs.astral.sh/uv/getting-started/installation/).
You can also use a different package manager that can read pyproject.toml.

To write audio files, you also need FFmpeg:

```sh
apt-get install ffmpeg
```

You need an API key for a provider of your choice.
The used model depends on what keys you export, for example:

```sh
export GEMINI_API_KEY=your_key_here
```

You can use:

- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY` and `ELEVENLABS_API_KEY` (text and speech)
- `OPENAI_API_KEY`

You can also use other models, see [llm.py](../bespoke/llm.py).
The quality of generated cards varies between providers and models.

## Quality checks

Before you start the full pipeline, you may want to check if your LLM provider
generates cards of sufficient quality for your target language.
How enjoyable and useful learning is depends on the quality of the cards.
Sentence creation and tagging are the most challenging parts of card creation
for LLMs, in our experience. You can create example data with:

```sh
uv run -m maintainers.sentence_quality --target="Japanese" --difficulty=B1 --cards_per_call=8
```

Alternatively, run the pipeline for a few minutes and inspect the output.

## Running the pipeline

The longest running and most expensive part is:

```sh
uv run create.py --target="Japanese" --native="English"
```

You can wait for the command to finish, or kill it whenever you feel like the
number of cards suffices. You can also adjust the size of the dataset with
`--cards_per_unit` and `--max_difficulty`.

When done, you can see statistics about your deck with:

```sh
uv run -m maintainers.card_distribution --target="Japanese" --native="English"
```

This tool will tell you if any words in your vocabulary are not covered by the
generated cards, or any files got corrupted.

The recommended, but optional, next step is to generate translations for all
words to show during learning:

```sh
uv run -m maintainers.translate_units --target="Japanese" --native="English"
```

Until here, the generated files are JSON, CSV and OGG. You can inspect or
manipulate them with any tool or process you like. The Python UI for learning
can also directly work with these files. However, for Android or publishing,
packaging the files into a database is necessary:

```sh
uv run -m maintainers.package_cards --target="Japanese" --native="English"
uv run -m maintainers.verify_package cards/japanese_(english).db
```

The command that verifies decks can be run anytime on databases you receive to
check integrity. The final output of this pipeline is `cards/japanese_(english).db`.
You can upload this file into the Android app and start learning.
