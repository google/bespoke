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

You need ffmpeg installed and a Gemini API key. Set it and run:

```
apt-get install ffmpeg
export GEMINI_API_KEY=your_key_here
uv run create.py --target="Japanese" --native="English"
```

You can also use other LLMs if you replace the implementations in
`bespoke/llm.py`.

## How to start learning

First, you need to either create or import cards for your language.
From here on, you won't need ffmpeg and a Gemini API key anymore.
Run this command and a tab should open in your web browser:

```
uv run learn.py --target="Japanese" --native="English" --difficulty=A1 --use_read_mode
```

## Supported languages

You can find instructions in [languages.py](bespoke/languages.py) to add
languages, both as a target for learning and your native language.

For the target parameter above, try:

- "Japanese"
- "Simplified Chinese"
- "Traditional Chinese"

## Disclaimer

This is not an officially supported Google product.
This project is not eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
