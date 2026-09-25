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

## Card creation

To start learning, you need a dataset of cards, and an app to learn with them.

### Existing datasets

This collection grows as more cards are generated.

Download the dataset on your Android phone, or laptop, from these sources:

| Language Pair | Kaggle Dataset |
| :------------ | :------------- |
| German → Traditional Chinese | [bespoke-cards-german-tradchinese](https://www.kaggle.com/datasets/google/bespoke-cards-german-tradchinese) |
| English → German | [bespoke-cards-english-german](https://www.kaggle.com/datasets/google/bespoke-cards-english-german) |

For Android, use the import function of the app.
For Python, copy the `.db` file into `cards/`.

### Generate your own dataset

If you don't find a dataset that fits your needs, follow the
[manual for our LLM pipeline](docs/generation.md) to generate your own dataset.

## Learning

Once you have a dataset ready, you can use one of our apps to select and show
cards for learning. There are two options:

- A Python frontend that opens a browser tab.
- An Android app.

### Python frontend

You can use [uv](https://docs.astral.sh/uv/getting-started/installation/)
to run the Python code, for example:

```sh
uv run learn.py --target="Japanese" --native="English" --difficulty=A1 --use_read_mode
```

Due to browser restrictions, the first card will not autoplay sound.
All cards after the first will work as expected.

### Android app

An Android app with the same features as the Python code is under development.
To build it, see the [developer manual](docs/maintainers.md).
You can upload a .db file into the app to start learning.

Note: If you upload a dataset into the app, it will make a copy.
You can save space by deleting the downloaded dataset afterwards.

<img alt="Android app" src="docs/android_app.png" width="540px">

### Backups

Bespoke does not store or synchronize your data. After cards are generated, it
runs fully offline. This also means that you are responsible for not losing your
progress. You may want to regularly copy and save the file `deck_<language>.json`
to a secure location of your choice. To learn on a new device, simply copy the
file over.

The Android app regularly exports the progress into your phone storage.
You can upload these files on the starting screen of the app on a new phone to
continue learning.

Currently, learning on two devices simultaneously is discouraged.
You would need to copy the progress file back and forth.

## Disclaimer

This is not an officially supported Google product.
This project is not eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
