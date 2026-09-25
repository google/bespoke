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

"""Translation operations for vocabulary units."""

from __future__ import annotations

import asyncio

from bespoke import languages, llm
from bespoke.unit import DictionaryUnit, Unit, WordUnit

MAX_RESPONSE_LENGTH = 100


def validate_translation(text: str) -> bool:
    """Validates that translation text does not contain invalid characters or length."""
    text = text.strip()
    if not text:
        return False
    if any(char in text for char in ["[", "]", "(", ")", "*", "\n", "\r"]):
        return False
    return len(text) <= MAX_RESPONSE_LENGTH


def _build_unit_translation_prompt(
    unit: Unit,
    target_language: languages.Language,
    native_language: languages.Language,
    name_to_definitions: dict[str, list[str]] | None = None,
) -> str:
    """Builds prompt for translating a single Unit to native language."""
    target = target_language.writing_system
    native = native_language.writing_system
    name = unit.name()

    if isinstance(unit, WordUnit):
        task = f"Translate the word '{name}' into {native}."
        instructions = f"Provide only the direct translation equivalents in {native}."
    elif isinstance(unit, DictionaryUnit):
        task = (
            f"Translate the word '{name}' into {native}.\n"
            f"The specific meaning referred to is defined as: "
            f"'{unit.definition()}'."
        )
        if name_to_definitions:
            other_definitions = [
                d for d in name_to_definitions.get(name, []) if d != unit.definition()
            ]
            if other_definitions:
                definitions_list = "\n".join(f"- '{d}'" for d in other_definitions)
                task += (
                    f"\n\nNote that the word '{name}' has other meanings defined "
                    f"as follows:\n{definitions_list}\n"
                    "Your translation MUST NOT cover those other meanings. "
                    "Choose translations that apply specifically to the target "
                    "meaning only."
                )
        instructions = (
            f"Provide the most precise translation in {native} that fits "
            f"the definition. Do NOT translate the definition itself. "
            f"Translate only the word '{name}'."
        )
    else:
        raise TypeError(f"Unknown unit type: {type(unit)}")

    return (
        f"You are a lexicographer translating from {target} to {native}.\n"
        f"{task}\n\n"
        "Rules:\n"
        f"1. {instructions}\n"
        "2. Separate multiple synonyms with commas.\n"
        f"3. Do NOT include the original word '{name}' or any {target} "
        "characters in your response.\n"
        "4. Do NOT include any pronunciation, or phonetics.\n"
        "5. Do NOT include grammatical labels, parts of speech, gender "
        "abbreviations, or explanations (do NOT write 'Noun', 'Verb', "
        "'(f)', '(m)', etc.).\n"
        "6. Do NOT use markdown formatting (no bold, no italics, "
        "no asterisks).\n"
        "7. The output must be on a single line.\n"
        f"8. The output must not exceed {MAX_RESPONSE_LENGTH} characters.\n\n"
        "9. The output will be automatically processed, return no other text.\n"
    )


@llm.standard_retry
async def _translate_single_unit(
    prompt: str,
    llm_client: llm.LlmClient,
) -> str:
    raw_translated = await llm_client.text_call(prompt, lower_safety=True)
    candidate = raw_translated.strip().strip("\"'“”«»‘`")
    if not validate_translation(candidate):
        raise ValueError(f"Invalid translation output: {candidate}")
    return candidate


async def translate_unit(
    unit: Unit,
    target_language: languages.Language,
    llm_client: llm.LlmClient,
    native_language: languages.Language,
    results: dict[str, str],
    name_to_definitions: dict[str, list[str]] | None = None,
) -> None:
    """Translates a single unit with retries and writes into results dictionary."""
    prompt = _build_unit_translation_prompt(
        unit=unit,
        target_language=target_language,
        native_language=native_language,
        name_to_definitions=name_to_definitions,
    )

    try:
        translated = await _translate_single_unit(prompt, llm_client)
        results[unit.id()] = translated
    except Exception:  # noqa: BLE001
        print(f"Failed to translate unit {unit.id()}")


async def translate_units(
    units: list[Unit],
    target_language: languages.Language,
    native_language: languages.Language,
    llm_client: llm.LlmClient,
    existing_translations: dict[str, str] | None = None,
    parallelism: int = 16,
) -> dict[str, str]:
    """Translates a collection of units concurrently."""
    name_to_definitions: dict[str, list[str]] = {}
    for u in units:
        if isinstance(u, DictionaryUnit):
            name_to_definitions.setdefault(u.name(), []).append(u.definition())

    results: dict[str, str] = {}
    if existing_translations:
        results.update(existing_translations)

    units_to_translate = [u for u in units if not results.get(u.id(), "").strip()]
    if not units_to_translate:
        return results

    semaphore = asyncio.Semaphore(parallelism)
    try:
        async with asyncio.TaskGroup() as tg:
            for unit in units_to_translate:
                await semaphore.acquire()

                async def run_task(u: Unit = unit) -> None:
                    try:
                        await translate_unit(
                            u,
                            target_language,
                            llm_client,
                            native_language,
                            results,
                            name_to_definitions,
                        )
                    finally:
                        semaphore.release()

                tg.create_task(run_task())
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Translation run was cancelled/interrupted.")
        raise

    return results
