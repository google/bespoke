<img alt="Bespoke logo" src="docs/icon.png" width="200px">

# Bespoke Language Learning

Bespoke is a language learning tool that helps you both memorize and apply
vocabulary in context. Powered by spaced repetition, users are shown sentences
that connect words that need practice.

Generative AI can help you create large amounts of custom flashcards for any
language pair. Or, if a dataset already exists, jump straight into learning!

Compared to existing flashcard software, this tool is specialized for
languages, with the following advantages:

- Depth: Beyond pure memorization, you learn to use vocabulary in sentences.
- Efficiency: A flashcard can have more than one learnable unit.
- Cohesion: Supports receptive (listen/read) and expressive (speak/write)
  skills. It adjusts your review schedule to account for cross-pollination. 🐝

Bespoke is experimental, and we are still learning how to learn better.

## Overview

The project consists of 2 parts:

- The LLM calls to generate the collection of learning cards.
- A simple frontend that selects and shows cards to the user.

## How to create cards

The commands below run Bespoke with
[uv](https://docs.astral.sh/uv/getting-started/installation/).
You can also use a different package manager that can read pyproject.toml.

You may skip the rest of this section if you find your languages in
[Existing datasets](#existing-datasets).

You need FFmpeg installed and an API key.
Depending on what keys you export, the model will be chosen.
You can use:

- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY` and `ELEVENLABS_API_KEY` (text and speech)
- `OPENAI_API_KEY`

Example run commands:

```
apt-get install ffmpeg
export GEMINI_API_KEY=your_key_here
uv run create.py --target="Japanese" --native="English"
```

You can also use other models, see [llm.py](bespoke/llm.py).
The quality of generated cards varies between providers and models.

## How to start learning

First, you need to either create or import cards for your language.
From here on, you won't need FFmpeg or your API key anymore.
Run this command and a tab should open in your web browser:

```
uv run learn.py --target="Japanese" --native="English" --difficulty=A1 --use_read_mode
```

After learning your first card, you can keep learning with a simple
`uv run learn.py`, or use the full command to choose languages, difficulty and
modes.

Due to browser restrictions, the first card will not autoplay sound.
All cards after the first will work as expected.

## Supported languages

You can find instructions in [languages.py](bespoke/languages.py) to add
languages, both as a target for learning and your native language.

For the target parameter above, try:

- "German"
- "Japanese"
- "Simplified Chinese"
- "Traditional Chinese"

## Existing datasets

This collection grows as more cards are generated.

You can download any of the existing datasets automatically using, e.g.:

```
uv run download.py --target="Traditional Chinese" --native="German"
```

| Language Pair | Kaggle Dataset |
| :------------ | :------------- |
| German → Traditional Chinese | [bespoke-cards-german-tradchinese](https://www.kaggle.com/datasets/google/bespoke-cards-german-tradchinese) |
| English → German | [bespoke-cards-english-german](https://www.kaggle.com/datasets/google/bespoke-cards-english-german) |
| Simplified Chinese → German | [bespoke-cards-german-simpchinese](https://www.kaggle.com/datasets/google/bespoke-cards-simpchinese-german) |

Alternatively, if you prefer to download manually, you can obtain the `.zip`
file directly from the links in the table above. Download the dataset into the
`cards/` directory and extract it:

```
cd cards/
unzip dataset_filename.zip
```

Ensure the `cards/` directory contains `index_trad_chinese_german.json` and
`trad_chinese_german/`.

## Backups

Bespoke does not store or synchronize your data. After cards are generated, it
runs fully offline. This also means that you are responsible for not losing your
progress. You may want to regularly copy and save the file `deck_LANGUAGE.json`
to a secure location of your choice. To learn on a new device, simply copy the
file over.

At the time, learning on two devices is therefore discouraged. You would need to
copy the progress file back and forth.

## Disclaimer

This is not an officially supported Google product.
This project is not eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
