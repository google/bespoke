# <img alt="Bespoke logo" src="docs/icon.png" width="200px">

# Bespoke Language Learning

This is an experimental language learning app using generative AI.
You listen to, speak, read or write sentences.
These sentences are chosen to show you vocabulary with spaced repetition.

## Overview

The project consists of 2 parts:

- The LLM calls to generate the collection of learning cards.
- A simple frontend that selects and shows cards to the user.

## How to create cards

The command below runs Bespoke with
[uv](https://docs.astral.sh/uv/getting-started/installation/).
You can also use a different package manager that can read pyproject.toml.

You need ffmpeg installed and an API key.
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
From here on, you won't need ffmpeg or your API key anymore.
Run this command and a tab should open in your web browser:

```
uv run learn.py --target="Japanese" --native="English" --difficulty=A1 --use_read_mode
```

After learning your first card, your can keep learning with a simple
`uv run learn.py`, or use the full command to choose languages, difficulty and
modes.

Due to browser restrictions, the first card will not auto play sound.
All cards after the first will work as expected.

## Supported languages

You can find instructions in [languages.py](bespoke/languages.py) to add
languages, both as a target for learning and your native language.

For the target parameter above, try:

- "German"
- "Japanese"
- "Simplified Chinese"
- "Traditional Chinese"

## Disclaimer

This is not an officially supported Google product.
This project is not eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
