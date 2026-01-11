# <img alt="Bespoke logo" src="docs/icon.png" width="200px">

# Bespoke Language Learning

This is an experimental language learning app using generative AI.
You listen to, speak, read or write sentences.
These sentences are chosen to show you vocabulary with spaced repetition.

## Architecture

The project consists of 2 parts:

- The LLM calls to generate the collection of learning cards.
- The frontend that selects and shows cards to the user.

This repository only contains the card generation.

## How to run

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

## Supported languages

You can find instructions in [languages.py](bespoke/languages.py) to add
languages, both as a target for learning and your native language.

## Disclaimer

This is not an officially supported Google product.
This project is not eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
