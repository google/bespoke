package com.google.bespoke

import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.File

class DeckEngineTest {

    companion object {
        const val DAY = 24.0 * 60.0 * 60.0
    }

    private lateinit var units: List<UnitItem>
    private lateinit var cards: List<Card>
    private lateinit var cardsByUnitId: Map<String, List<Card>>
    private lateinit var deck: DeckEngine

    @Before
    fun setUp() {
        units = listOf(
            WordUnit("unit_a1_0", Difficulty.A1),
            WordUnit("unit_a1_1", Difficulty.A1),
            WordUnit("unit_a1_2", Difficulty.A1),
            WordUnit("unit_a2_0", Difficulty.A2),
            WordUnit("unit_b1_0", Difficulty.B1),
            DictionaryUnit("homonym", "definition1", Difficulty.A1)
        )

        cards = listOf(
            Card(
                id = "card_0",
                sentence = "unit_a1_0",
                native_sentence = "Unit A1 0",
                audio_filename = "audio_0.ogg",
                slow_audio_filename = "slow_0.ogg",
                native_audio_filename = "native_0.ogg",
                unit_tags = listOf(UnitTag("unit_a1_0", "unit_a1_0"))
            ),
            Card(
                id = "card_1",
                sentence = "unit_a1_1",
                native_sentence = "Unit A1 1",
                audio_filename = "audio_1.ogg",
                slow_audio_filename = "slow_1.ogg",
                native_audio_filename = "native_1.ogg",
                unit_tags = listOf(UnitTag("unit_a1_1", "unit_a1_1"))
            ),
            Card(
                id = "card_2",
                sentence = "unit_a1_2",
                native_sentence = "Unit A1 2",
                audio_filename = "audio_2.ogg",
                slow_audio_filename = "slow_2.ogg",
                native_audio_filename = "native_2.ogg",
                unit_tags = listOf(UnitTag("unit_a1_2", "unit_a1_2"))
            ),
            Card(
                id = "card_3",
                sentence = "unit_a2_0",
                native_sentence = "Unit A2 0",
                audio_filename = "audio_3.ogg",
                slow_audio_filename = "slow_3.ogg",
                native_audio_filename = "native_3.ogg",
                unit_tags = listOf(UnitTag("unit_a2_0", "unit_a2_0"))
            ),
            Card(
                id = "card_4",
                sentence = "unit_b1_0",
                native_sentence = "Unit B1 0",
                audio_filename = "audio_4.ogg",
                slow_audio_filename = "slow_4.ogg",
                native_audio_filename = "native_4.ogg",
                unit_tags = listOf(UnitTag("unit_b1_0", "unit_b1_0"))
            ),
            Card(
                id = "card_5",
                sentence = "homonym",
                native_sentence = "Homonym Def 1",
                audio_filename = "audio_5.ogg",
                slow_audio_filename = "slow_5.ogg",
                native_audio_filename = "native_5.ogg",
                unit_tags = listOf(UnitTag("homonym", "homonym - definition1"))
            )
        )

        cardsByUnitId = mapOf(
            "unit_a1_0" to listOf(cards[0]),
            "unit_a1_1" to listOf(cards[1]),
            "unit_a1_2" to listOf(cards[2]),
            "unit_a2_0" to listOf(cards[3]),
            "unit_b1_0" to listOf(cards[4]),
            "homonym - definition1" to listOf(cards[5])
        )

        deck = DeckEngine(
            targetLanguageCode = "test_lang",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = cardsByUnitId,
            translations = mapOf("unit_a1_0" to "Unit 0 Translation"),
            unitLookup = units.associateBy { it.id() }
        )
    }

    @Test
    fun testDraw() {
        deck.setModes(listOf(Mode.LISTEN, Mode.SPEAK))
        val (mode, card) = deck.draw()
        assertEquals(Mode.LISTEN, mode)
        assertEquals("unit_a1_0", card.sentence)
    }

    @Test
    fun testRate() {
        deck.setModes(listOf(Mode.LISTEN, Mode.SPEAK))
        val (mode, card) = deck.draw()
        assertEquals(listOf("unit_a1_0"), card.unitIds())
        deck.rate(units[0], mode, 3)
        val (_, nextCard) = deck.draw()
        assertEquals(listOf("unit_a1_1"), nextCard.unitIds())
    }

    @Test
    fun testAssumeKnown() {
        deck.setAssumeKnown(Difficulty.A2)
        val (_, card) = deck.draw()
        assertEquals("unit_b1_0", card.sentence)
    }

    @Test
    fun testIntroduceFirstCard() {
        val firstUnit = units[0]
        val (mode, card) = deck.draw(currentTime = 1.0)
        assertEquals(firstUnit.id(), card.unit_tags[0].unit_id)
        deck.rate(firstUnit, mode, 3, currentTime = 2.0)
        val (_, nextCard) = deck.draw(currentTime = 3.0)
        assertNotEquals(firstUnit.id(), nextCard.unit_tags[0].unit_id)
    }

    @Test
    fun testDrawFailedUnit() {
        val subset = units.subList(0, 3)
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        deck.setModes(allModes)

        for (days in listOf(0.0, 100.0)) {
            for ((i, mode) in allModes.withIndex()) {
                for (unit in subset) {
                    deck.rate(unit, mode, 3, currentTime = DAY * (days + i))
                }
            }
        }

        val unit2 = subset[1]
        deck.rate(unit2, Mode.SPEAK, 1, currentTime = DAY * 200)
        val (mode, card) = deck.draw(currentTime = DAY * 201)
        assertEquals(unit2.id(), card.unit_tags[0].unit_id)
        assertEquals(Mode.SPEAK, mode)
    }

    @Test
    fun testDrawUnblockedMode() {
        val subset = units.subList(0, 3)
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        deck.setModes(allModes)

        for (days in listOf(0.0, 100.0)) {
            for ((i, mode) in allModes.withIndex()) {
                for (unit in subset) {
                    deck.rate(unit, mode, 3, currentTime = DAY * (days + i))
                }
            }
        }

        val unit2 = subset[1]
        deck.rate(unit2, Mode.LISTEN, 1, currentTime = DAY * 200)
        deck.rate(unit2, Mode.SPEAK, 1, currentTime = DAY * 200)

        val (mode, card) = deck.draw(currentTime = DAY * 201)
        assertEquals(unit2.id(), card.unit_tags[0].unit_id)
        assertTrue(mode == Mode.LISTEN || mode == Mode.SPEAK)
    }

    @Test
    fun testIntroduceNewWhenUrgentIsBlocked() {
        val subset = units.subList(0, 3)
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        deck.setModes(allModes)

        for (days in listOf(0.0, 100.0)) {
            for ((i, mode) in allModes.withIndex()) {
                for (unit in subset.subList(0, 2)) {
                    deck.rate(unit, mode, 3, currentTime = DAY * (days + i))
                }
            }
        }

        val unit2 = subset[1]
        val unit3 = subset[2]
        deck.rate(unit2, Mode.LISTEN, 1, currentTime = DAY * 200)
        deck.rate(unit2, Mode.LISTEN, 0, currentTime = DAY * 201 - 1)
        val (_, card) = deck.draw(currentTime = DAY * 201)
        assertEquals(unit3.id(), card.unit_tags[0].unit_id)
    }

    @Test
    fun testStats() {
        deck.setModes(listOf(Mode.LISTEN, Mode.SPEAK))
        val unit1 = units[0]
        val unit2 = units[1]
        val unit3 = units[2]

        deck.rate(unit1, Mode.LISTEN, 3, currentTime = DAY * 0)
        deck.rate(unit1, Mode.SPEAK, 3, currentTime = DAY * 1)
        deck.rate(unit1, Mode.LISTEN, 3, currentTime = DAY * 100)
        deck.rate(unit1, Mode.SPEAK, 3, currentTime = DAY * 101)
        deck.rate(unit2, Mode.LISTEN, 1, currentTime = DAY * 0.0)
        deck.rate(unit2, Mode.LISTEN, 3, currentTime = DAY * 0.5)
        deck.rate(unit2, Mode.SPEAK, 1, currentTime = DAY * 1.0)
        deck.rate(unit2, Mode.SPEAK, 3, currentTime = DAY * 1.5)
        deck.rate(unit3, Mode.LISTEN, 1, currentTime = DAY * 90)
        deck.rate(unit3, Mode.SPEAK, 1, currentTime = DAY * 91)
        deck.rate(unit3, Mode.LISTEN, 3, currentTime = DAY * 100)
        deck.rate(unit3, Mode.SPEAK, 3, currentTime = DAY * 101)

        val stats = deck.stats(currentTime = DAY * 102)
        assertEquals(1, stats.waiting)
        assertEquals(2, stats.known)
        assertEquals(1, stats.mature)
    }

    @Test
    fun testScoreCardPenaltiesAndBonuses() {
        val card = cards[0]
        // Base untouched penalty: -200.0 + difficulty match: +0.1 = -199.9
        val initialScore = deck.scoreCard(card, Mode.LISTEN, currentTime = 100.0)
        assertEquals(-199.9, initialScore, 1e-3)

        // Add reported usage: -1000000.0
        deck.logUsage(card.id, isReported = true, currentTime = 100.0)
        val reportedScore = deck.scoreCard(card, Mode.LISTEN, currentTime = 100.0)
        assertTrue(reportedScore < -1000000.0)
    }

    @Test
    fun testSaveAndLoadState() {
        val unit = units[0]
        deck.rate(unit, Mode.LISTEN, 3, currentTime = 100.0)
        deck.logUsage("card_0", isReported = false, currentTime = 100.0)
        deck.setDifficulty(Difficulty.B2)
        deck.setAssumeKnown(Difficulty.A2)

        val json = deck.saveJson()
        assertTrue(json.contains("test_lang"))
        assertTrue(json.contains("unit_a1_0"))
        assertTrue(json.contains("B2"))

        val newDeck = DeckEngine(
            targetLanguageCode = "test_lang",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = cardsByUnitId,
            translations = emptyMap(),
            unitLookup = units.associateBy { it.id() }
        )
        newDeck.loadJson(json)
        assertEquals(Difficulty.B2, newDeck.getDifficulty())
        assertEquals(Difficulty.A2, newDeck.getAssumeKnown())
        assertEquals(1, newDeck.getRatingStates().size)
        assertEquals(1, newDeck.getCardUsages().size)
    }
}
