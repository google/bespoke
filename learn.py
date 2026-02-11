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

"""Simple user interface for learning."""

import argparse
from nicegui import ui
import os
from pathlib import Path
import sys

from bespoke import Deck
from bespoke import Difficulty
from bespoke import Mode
from bespoke import languages


COLOR_MAP = {
    3: "positive",  # Green
    2: "warning",  # Yellow
    1: "negative",  # Red
    0: "info",  # Blue
}
SCORE_ROTATION = {
    0: 3,
    1: 0,
    2: 1,
    # We skip 2 intentionally, currently not supported.
    3: 1,
}


class RatingWebApp:
    def __init__(self, deck: Deck, deck_filename: str) -> None:
        self._deck = deck
        self._deck_filename = deck_filename
        self._ratings = {}

        self.main_container = ui.column().classes(
            "w-full max-w-2xl mx-auto items-center gap-4 p-4"
        )

        self._load_next_card()

    def _load_next_card(self) -> None:
        self._mode, self._card = self._deck.draw()
        self._show_front()

    def _render_sentence(self, text: str, large: bool = True) -> None:
        size_classes = "text-3xl p-5" if large else "text-lg p-2.5"
        html_content = f"""
            <div class="{size_classes} bg-white dark:bg-gray-700 rounded-lg
                text-black dark:text-white text-center font-sans shadow-md">
                {text}
            </div>
        """

        ui.html(html_content, sanitize=False)

    def _render_audio_player(
        self, label: str, filename: str, autoplay: bool = False
    ) -> None:
        with ui.row().classes("items-center gap-2"):
            ui.label(label).classes("font-bold w-16")
            if os.path.exists(filename):
                ui.audio(filename, autoplay=autoplay, controls=True)
            else:
                ui.icon("volume_off", color="grey").tooltip(f"Missing file: {filename}")

    def _create_color_cycling_button(self, word: str, unit: str) -> None:
        initial_rating = 0
        self._ratings[unit] = initial_rating
        btn = ui.button(word, on_click=lambda: cycle(btn))
        btn.props(f"color={COLOR_MAP[initial_rating]} push")

        def cycle(b):
            rating = SCORE_ROTATION.get(self._ratings[unit], initial_rating)
            self._ratings[unit] = rating
            b.props(f"color={COLOR_MAP[rating]}")

        return btn

    def _show_front(self) -> None:
        self.main_container.clear()

        with self.main_container:
            match self._mode:
                case Mode.LISTEN:
                    with ui.card().classes(
                        "w-full items-center bg-gray-100 dark:bg-zinc-800"
                    ):
                        self._render_audio_player(
                            "Play:", self._card.audio_filename, autoplay=True
                        )
                        self._render_audio_player(
                            "Slow:", self._card.slow_audio_filename
                        )
                case Mode.SPEAK:
                    ui.label("Speak the sentence!").classes(
                        "text-gray-500 dark:text-gray-400 text-xl font-mono"
                    )
                    with ui.card().classes(
                        "w-full items-center bg-gray-100 dark:bg-zinc-800"
                    ):
                        self._render_audio_player("", self._card.native_audio_filename)
                    self._render_sentence(self._card.native_sentence)
                case Mode.READ:
                    self._render_sentence(self._card.sentence)
                case Mode.WRITE:
                    ui.label("Write the sentence!").classes(
                        "text-gray-500 dark:text-gray-400 text-xl font-mono"
                    )
                    with ui.card().classes(
                        "w-full items-center bg-gray-100 dark:bg-zinc-800"
                    ):
                        self._render_audio_player("", self._card.native_audio_filename)
                    self._render_sentence(self._card.native_sentence)

            ui.separator().classes("my-4")

            stats = self._deck.stats()
            satisfied = stats["satisfied"]
            waiting = stats["waiting"]
            with ui.row().classes("w-full justify-end gap-2 mb-2"):
                ui.badge(f"Known: {satisfied}", color="grey").props("outline")
                ui.badge(f"To Do: {waiting}", color="grey").props("outline")

            ui.button("Flip", on_click=self._show_back).classes("w-full h-12 text-lg")

    def _show_back(self) -> None:
        self.main_container.clear()

        with self.main_container:
            # 1. Playback Section
            with ui.card().classes("w-full items-center bg-gray-100 dark:bg-zinc-800"):
                autoplay = self._mode != Mode.LISTEN
                self._render_audio_player(
                    "Play:", self._card.audio_filename, autoplay=autoplay
                )
                self._render_audio_player("Slow:", self._card.slow_audio_filename)
                self._render_audio_player("Native:", self._card.native_audio_filename)

            # 2. Text Section
            self._render_sentence(self._card.sentence)
            if self._card.phonetic:
                ui.label(self._card.phonetic).classes(
                    "text-gray-500 dark:text-gray-400 text-xl font-mono"
                )
            self._render_sentence(self._card.native_sentence, large=False)

            # 3. Rating Section
            ui.label("Rate specific words:").classes(
                "text-sm text-gray-400 dark:text-gray-300 mt-4"
            )
            row_container = ui.row().classes("wrap justify-center gap-2 w-full")
            all_buttons = []

            with row_container:
                for part, unit in self._card.split_into_parts():
                    if unit is None:
                        ui.label(part).classes("self-center text-lg p-2")
                    else:
                        with ui.column().classes("items-center gap-0"):
                            btn = self._create_color_cycling_button(part, unit)
                            all_buttons.append((unit, btn))
                            ui.label(unit).classes(
                                "text-[10px] text-[#888] dark:text-gray-400"
                            )

            # 4. Controls
            ui.separator().classes("my-4")
            with ui.row().classes("w-full justify-between"):

                def make_all_green():
                    for unit, btn in all_buttons:
                        self._ratings[unit] = 3
                        btn.props(f"color={COLOR_MAP[3]}")

                ui.button("All Success", on_click=make_all_green).props(
                    "outline color=positive"
                )
                report_switch = ui.switch("Report Error")

            ui.button(
                "Next", on_click=lambda: self._finalize(report_switch.value)
            ).props("color=primary size=lg").classes("w-full")

    def _finalize(self, is_reported) -> None:
        for unit, rating in self._ratings.items():
            self._deck.rate(unit, self._mode, rating)
        self._deck.log_usage(self._card.id, is_reported=is_reported)
        self._deck.save(self._deck_filename)

        self._ratings = {}
        self._load_next_card()


def open_latest_deck() -> tuple[Deck | None, str]:
    paths = list(Path(".").glob("deck_*.json"))
    if not paths:
        return None, ""
    latest_filename = str(max(paths, key=lambda f: os.path.getmtime(f)))
    deck = Deck.load(latest_filename)
    return deck, latest_filename


def open_deck() -> tuple[Deck, str]:
    if len(sys.argv) == 1:
        deck, filename = open_latest_deck()
        if deck is not None:
            print(f"Continuing with '{filename}'")
            return deck, filename

    parser = argparse.ArgumentParser(description="Learn language cards.")
    target_choices = {}
    for code_name in languages.LANGUAGE_DATA:
        language = languages.LANGUAGES[code_name]
        target_choices[language.writing_system] = language
    native_choices = {
        lang.writing_system: lang for lang in languages.LANGUAGES.values()
    }
    difficulties = [str(d) for d in Difficulty]
    parser.add_argument(
        "--target",
        type=str,
        choices=list(target_choices),
        required=True,
        help="The language you are learning.",
    )
    parser.add_argument(
        "--native",
        type=str,
        choices=list(native_choices),
        required=True,
        help="A language that you know.",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        choices=list(difficulties),
        required=True,
        help="A language that you know.",
    )
    parser.add_argument("--use_read_mode", action="store_true", help="Enable read mode")
    parser.add_argument(
        "--use_write_mode", action="store_true", help="Enable write mode"
    )
    args = parser.parse_args()

    target = target_choices[args.target]
    native = native_choices[args.native]
    difficulty = Difficulty(args.difficulty)
    modes = [Mode.LISTEN, Mode.SPEAK]
    if args.use_read_mode:
        modes.append(Mode.READ)
    if args.use_write_mode:
        modes.append(Mode.WRITE)

    deck_filename = f"deck_{target.code_name}.json"
    if not os.path.isfile(deck_filename):
        print("Creating a new deck...")
        deck = Deck(target, native)
        deck.save(deck_filename)
    else:
        deck = Deck.load(deck_filename)
    deck.set_difficulty(difficulty)
    deck.set_modes(modes)

    return deck, deck_filename


deck, deck_filename = open_deck()


@ui.page("/")
def index():
    ui.dark_mode(value="auto")
    ui.query("body").classes("bg-gray-50 dark:bg-zinc-900 m-0 p-0")
    with ui.column().classes("w-full items-center p-8"):
        ui.label("Bespoke").classes(
            "text-3xl font-light text-gray-600 dark:text-gray-300 mb-6"
        )
        RatingWebApp(deck, deck_filename)


ui.run(title="Bespoke", favicon="🐝")
