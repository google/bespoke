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

"""Main file to create cards."""

import argparse
import datetime

from bespoke import Deck
from bespoke import languages


def show_ratings(deck: Deck, unit: str) -> None:
    print(f"Stats for {unit}...")
    ratings = deck._ratings.get(unit, [])
    if ratings:
        print("Ratings:")
    for rating in ratings:
        print(str(rating))
    print("")


def show_cards(deck: Deck) -> None:
    print(
        (
            f"Deck from {deck._target_language.writing_system} "
            f"to {deck._native_language.writing_system}"
        )
    )
    modes = [str(m) for m in deck._modes]
    print(f"Selected difficulty {deck._difficulty} and modes {modes}")
    if deck._assume_known is not None:
        print(f"Assumes knowledge of {deck._assume_known} vocabulary")
    stats = deck.stats()
    print(f"Waiting: {stats['waiting']}, Satisfied: {stats['satisfied']}")
    print("")

    current_time = datetime.datetime.now().timestamp()
    urgency_states = deck._compute_urgencies(current_time)
    mode, unit_id = deck._choose_task(urgency_states)
    print(f"Next unit is '{unit_id}'")
    state = urgency_states[unit_id]
    print(f"        Is touched: {state.is_touched}")
    print(f"Needs introduction: {state.needs_introduction}")
    print(f"         Is target: {state.is_target}")
    print(f"           Urgency: {state.urgency}")
    print(f"              Mode: {state.mode}")
    print("")

    unit = deck._target_language.get_by_id(unit_id)
    cards = []
    if unit:
        cards = deck._card_index.cards(unit)
    card_scores = []
    for card in cards:
        score = deck._score_card(card, urgency_states, current_time)
        card_scores.append((card, score))
    card_scores.sort(key=lambda x: x[1])
    for card, score in card_scores[-5:]:
        card_usages = deck._card_id_uses.get(card.id, [])
        if any(usage.is_reported for usage in card_usages):
            reported = " (reported)"
        else:
            reported = ""
        print((f"Score {score:.1f} - {len(card_usages)}x{reported} for {str(card)}"))


def main():
    parser = argparse.ArgumentParser(description="Create language cards.")
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
    parser.add_argument("--unit", type=str, help="The unit to inspect.")
    args = parser.parse_args()

    target = target_choices[args.target]
    deck_filename = f"deck_{target.code_name}.json"
    deck = Deck.load(deck_filename)
    if args.unit is not None:
        show_ratings(deck, args.unit)
    show_cards(deck)


if __name__ == "__main__":
    main()
