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

"""Script to check sentence generation quality and tagging."""

import argparse
import asyncio

from bespoke import Difficulty
from bespoke import Language
from bespoke import builder
from bespoke import languages
from bespoke import llm
from bespoke import tagger


async def tag_and_format(
    sentence: str,
    units: list,
    language: Language,
    llm_client: llm.LlmClient,
    producer: builder.SentenceProducer,
    native_language: Language | None = None,
    check_rejection: bool = False,
) -> str:
    unit_tags = await tagger.create_tags(
        sentence=sentence,
        hint=units,
        language=language,
        llm_client=llm_client,
    )
    producer.register_card([tag.unit_id for tag in unit_tags])
    lines = [f"Sentence: {sentence}"]
    if check_rejection and native_language:
        native_sentence = await llm_client.translate(sentence, native_language)
        phonetic = await llm_client.to_phonetic(sentence, language)
        is_allowed = await llm_client.check_card(
            sentence=sentence,
            native_sentence=native_sentence,
            phonetic=phonetic,
            unit_tags=unit_tags,
            target_language=language,
            native_language=native_language,
        )
        lines.append(f"Translation: {native_sentence}")
        if phonetic:
            lines.append(f"Phonetic: {phonetic}")
        if not is_allowed:
            tag_details = ", ".join(f"{t.occurance}->{t.unit_id}" for t in unit_tags)
            phonetic_details = f", phonetic='{phonetic}'" if phonetic else ""
            lines.append(
                f"Rejection: Discarding invalid card: sentence='{sentence}', "
                f"translation='{native_sentence}'{phonetic_details}, "
                f"tags=[{tag_details}]"
            )
        else:
            lines.append("Rejection check: Allowed")
    lines.append("Tags:")
    for tag in unit_tags:
        lines.append(f"  {tag.occurance} -> {tag.unit_id}")

    current_idx = 0
    untagged_parts = []
    for tag in unit_tags:
        occurance = tag.occurance
        start_idx = sentence.find(occurance, current_idx)
        if start_idx != -1:
            gap = sentence[current_idx:start_idx]
            clean_gap = tagger.strip_punctuation_and_space(gap)
            if clean_gap:
                untagged_parts.append(clean_gap)
            current_idx = start_idx + len(occurance)

    gap = sentence[current_idx:]
    clean_gap = tagger.strip_punctuation_and_space(gap)
    if clean_gap:
        untagged_parts.append(clean_gap)

    if untagged_parts:
        lines.append(f"Untagged: {', '.join(untagged_parts)}")

    lines.append("--------------------------------------")
    return "\n".join(lines)


async def main_async():
    parser = argparse.ArgumentParser(description="Check sentence quality and tagging.")
    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
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
        help="A language that you know.",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default=None,
        choices=list(difficulties),
        help="Difficulty level of used vocabulary.",
    )
    parser.add_argument(
        "--cards_per_call",
        type=int,
        default=8,
        help="Number of cards per call",
    )
    parser.add_argument(
        "--check_rejection",
        action="store_true",
        help="Check if cards are rejected.",
    )

    args = parser.parse_args()

    if args.check_rejection and not args.native:
        parser.error("--native is required when --check_rejection is set.")

    real_language = target_choices[args.target]
    native_language = native_choices[args.native] if args.native else None
    grammar = languages.load_grammar(real_language.code_name)
    llm_client = llm.get_llm_client()

    if args.difficulty:
        difficulty = Difficulty(args.difficulty)
        all_units = real_language.units()
        filtered_units = [u for u in all_units if u.difficulty() == difficulty]
        if len(filtered_units) < args.cards_per_call:
            print(
                f"Found only {len(filtered_units)} units, need {args.cards_per_call}."
            )
            return

        target = Language(
            name=real_language.name,
            writing_system=real_language.writing_system,
            phonetic_system=real_language.phonetic_system,
            code_name=real_language.code_name,
        )
        target._units = filtered_units[: args.cards_per_call]
        target._units_by_id = {u.id(): u for u in target._units}
        target._units_by_name = {}
        for u in target._units:
            target._units_by_name.setdefault(u.name(), []).append(u)
        target._initialized = True
    else:
        target = real_language

    producer = builder.SentenceProducer(
        target,
        llm_client,
        grammar,
        cards_per_unit=1,
        cards_per_call=args.cards_per_call,
        num_existing_cards=0,
    )

    generated_count = 0
    while not producer.done():
        sentences, units, grammar_used = await producer.create()
        print(f"Grammar used: {grammar_used}")
        print("--------------------------------------")

        async with asyncio.TaskGroup() as tg:
            tasks = []
            for sentence in sentences:
                tasks.append(
                    tg.create_task(
                        tag_and_format(
                            sentence=sentence,
                            units=units,
                            language=real_language,
                            llm_client=llm_client,
                            producer=producer,
                            native_language=native_language,
                            check_rejection=args.check_rejection,
                        )
                    )
                )

        for task in tasks:
            print(task.result())
        generated_count += len(sentences)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
