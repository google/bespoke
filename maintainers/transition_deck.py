# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tool to transition old decks to new decks by updating unit IDs."""

import argparse
from pathlib import Path
import shutil

from bespoke import Deck
from bespoke import languages
from bespoke.unit import DictionaryUnit


def main():
    parser = argparse.ArgumentParser(description="Transition old deck to new deck.")
    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
            target_choices[language.writing_system] = language
    parser.add_argument(
        "--target",
        type=str,
        choices=list(target_choices),
        required=True,
        help="The language you are learning.",
    )
    args = parser.parse_args()
    target_language = target_choices[args.target]

    deck_path = Path(f"deck_{target_language.code_name}.json")
    if not deck_path.exists():
        print(f"Deck file not found: {deck_path}")
        return

    # Check that the language indeed has DictionaryUnit now
    units = target_language.units()
    if not units or not isinstance(units[0], DictionaryUnit):
        print(
            f"Language {args.target} does not use DictionaryUnit. No transition needed."
        )
        return

    # Map each word to its first DictionaryUnit ID
    word_to_unit_id = {}
    for u in units:
        if isinstance(u, DictionaryUnit):
            if u.name() not in word_to_unit_id:
                word_to_unit_id[u.name()] = u.id()

    print(f"Mapped {len(word_to_unit_id)} words to DictionaryUnit IDs.")

    deck = Deck.load(deck_path)

    # Update ratings
    new_ratings = {}
    conversions_made = 0
    for key, ratings in deck._ratings.items():
        if key in word_to_unit_id:
            new_key = word_to_unit_id[key]
            new_ratings[new_key] = ratings
            conversions_made += 1
        else:
            print(f"Warning: Word '{key}' not found in vocabulary. Removing.")

    deck._ratings = new_ratings

    # Backup the deck, then overwrite it
    if conversions_made > 0:
        backup_path = deck_path.with_suffix(deck_path.suffix + ".bak")
        shutil.copy(deck_path, backup_path)
        print(f"Backed up old deck to {backup_path}")
        deck.save(deck_path)
        print(
            f"Saved transitioned deck with {conversions_made} conversions to {deck_path}"
        )
    else:
        print("No unit IDs needed conversion. Deck not saved.")


if __name__ == "__main__":
    main()
