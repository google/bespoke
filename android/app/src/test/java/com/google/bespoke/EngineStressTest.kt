package com.google.bespoke

import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.srs.RatingState
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.exp
import kotlin.math.tanh

class EngineStressTest {

    companion object {
        const val MINUTE = 60.0
        const val HOUR = 3600.0
        const val DAY = 86400.0
    }

    // ==========================================
    // 1. SRS MATHEMATICAL MODEL ADVERSARIAL TESTS
    // ==========================================

    @Test
    fun testExtremeTimestamps() {
        val state = RatingState()

        // Zero timestamp
        state.add(Rating(mode = "listen", time = 0.0, score = 3))
        assertEquals(1, state.ratings().size)
        assertTrue(state.isTouched())
        assertTrue(state.isIntroduced(Mode.LISTEN))

        // Large timestamp (year 2038 / 2100 / far future)
        val farFuture = 2_000_000_000.0 // ~2033
        state.add(Rating(mode = "listen", time = farFuture, score = 3))
        assertEquals(2, state.ratings().size)

        // Urgency in extreme far future: 1e12
        val extremeFuture = 1_000_000_000_000.0
        val urgencyExtreme = state.urgency(Mode.LISTEN, extremeFuture)
        assertFalse(urgencyExtreme.isNaN())
        assertFalse(urgencyExtreme.isInfinite())
        assertTrue(urgencyExtreme <= 1.0)
        assertTrue(urgencyExtreme > 0.999999)

        // Microsecond delta ratings
        val microDeltaState = RatingState()
        val baseT = 1_700_000_000.0
        microDeltaState.add(Rating(mode = "speak", time = baseT, score = 1))
        microDeltaState.add(Rating(mode = "speak", time = baseT + 0.000001, score = 0))
        microDeltaState.add(Rating(mode = "speak", time = baseT + 0.000002, score = 1))
        assertEquals(3, microDeltaState.ratings().size)
    }

    @Test
    fun testNegativeAndOutOfOrderTimestampRejection() {
        val state = RatingState()
        state.add(Rating(mode = "read", time = 1000.0, score = 3))
        // Out of order timestamps should be rejected
        state.add(Rating(mode = "read", time = 500.0, score = 1))
        state.add(Rating(mode = "read", time = 0.0, score = 1))
        state.add(Rating(mode = "read", time = -100.0, score = 1))
        assertEquals(1, state.ratings().size)

        // Identical timestamp is allowed (not strictly decreasing)
        state.add(Rating(mode = "write", time = 1000.0, score = 3))
        assertEquals(2, state.ratings().size)
    }

    @Test
    fun testLongElapsedTimesAndAsymptotes() {
        val state = RatingState()
        val t0 = 100_000.0
        state.add(Rating(mode = "listen", time = t0, score = 3))

        // Urgency right before target
        val initialGreenStreak = RatingState.FULL_INITIAL_GREEN_INTERVAL
        val targetInterval = initialGreenStreak * RatingState.INTERVAL_FACTOR
        val target = t0 + targetInterval

        val uBefore = state.urgency(Mode.LISTEN, target - 1000.0)
        val uAtTarget = state.urgency(Mode.LISTEN, target)
        val uAfter = state.urgency(Mode.LISTEN, target + 1000.0)

        assertTrue(uBefore < 0.0)
        assertEquals(0.0, uAtTarget, 1e-9)
        assertTrue(uAfter > 0.0)

        // Urgency 10 years later
        val u10Years = state.urgency(Mode.LISTEN, target + 10 * 365 * DAY)
        assertTrue(u10Years > 0.9999)
        assertTrue(u10Years <= 1.0)
        assertFalse(u10Years.isNaN())

        // Urgency 1000 years later
        val u1000Years = state.urgency(Mode.LISTEN, target + 1000 * 365 * DAY)
        assertEquals(1.0, u1000Years, 1e-6)
    }

    @Test
    fun testRapidRatingFlipsAndOscillations() {
        val state = RatingState()
        var curTime = 10_000.0

        // Rapid alternating flips with time steps larger than block intervals
        for (i in 0 until 50) {
            curTime += RatingState.BLOCK_INTERVAL + 100.0
            state.add(Rating(mode = "listen", time = curTime, score = 1))
            curTime += RatingState.RED_BLOCK_INTERVAL + 100.0
            state.add(Rating(mode = "listen", time = curTime, score = 3))
        }

        assertEquals(100, state.ratings().size)
        assertTrue(state.isTouched())
        assertTrue(state.isIntroduced(Mode.LISTEN))

        // Check urgency after block expires
        val unblockTime = curTime + RatingState.BLOCK_INTERVAL + 1.0
        val u = state.urgency(Mode.LISTEN, unblockTime)
        assertFalse(u.isNaN())
        assertFalse(u.isInfinite())
        assertTrue(u in -1.0..1.0)
    }

    @Test
    fun testExtremeDecayStreak() {
        val state = RatingState()
        var curTime = 100_000.0

        // Initial green rating: streak = 14 days
        state.add(Rating(mode = "read", time = curTime, score = 3))

        // Advance time past the 20-hour block interval
        curTime += RatingState.BLOCK_INTERVAL + 10.0

        // 60 consecutive red ratings: streak decayed by 0.5^60
        for (i in 0 until 60) {
            curTime += RatingState.RED_BLOCK_INTERVAL + 10.0
            state.add(Rating(mode = "read", time = curTime, score = 1))
        }

        assertEquals(61, state.ratings().size)

        // After red, urgency is 1.0 when unblocked
        val testTime = curTime + RatingState.RED_BLOCK_INTERVAL + 10.0
        val u = state.urgency(Mode.READ, testTime)
        assertEquals(1.0, u, 1e-6)

        // Add a green rating after extreme decay
        curTime = testTime + 10.0
        state.add(Rating(mode = "read", time = curTime, score = 3))
        val nextU = state.urgency(Mode.READ, curTime + RatingState.BLOCK_INTERVAL + 100.0)
        assertFalse(nextU.isNaN())
        assertFalse(nextU.isInfinite())
        assertTrue(nextU in -1.0..1.0)
    }

    @Test
    fun testExactIntervalBoundaries() {
        val state = RatingState()
        val t0 = 10_000.0
        state.add(Rating(mode = "speak", time = t0, score = 3))

        val streak = RatingState.FULL_INITIAL_GREEN_INTERVAL // 1209600.0
        val targetInterval = streak * RatingState.INTERVAL_FACTOR // 2177280.0
        val target = t0 + targetInterval

        // Exact boundary checks
        assertEquals(0.0, state.urgency(Mode.SPEAK, target), 1e-12)
        assertTrue(state.urgency(Mode.SPEAK, target - 1e-6) < 0.0)
        assertTrue(state.urgency(Mode.SPEAK, target + 1e-6) > 0.0)

        // Block boundary checks: base block = BLOCK_INTERVAL (72000s)
        val maxGreen = streak
        val blockScale = 1.0 - exp(-maxGreen / RatingState.BLOCK_SCALE_INTERVAL)
        val blockInterval = maxOf(RatingState.BLOCK_INTERVAL * blockScale, RatingState.MINIMUM_BLOCK_INTERVAL)
        val blockEnd = t0 + blockInterval

        assertEquals(-1.0, state.urgency(Mode.SPEAK, blockEnd - 1e-6), 1e-12)
        val deviation = (blockEnd + 1e-6 - target) / targetInterval
        assertEquals(tanh(deviation), state.urgency(Mode.SPEAK, blockEnd + 1e-6), 1e-6)
    }

    @Test
    fun testMultiModeInterleavedHistories() {
        val state = RatingState()
        var curTime = 1000.0

        // Interleave LISTEN, SPEAK, READ, WRITE with proper unblocking intervals
        val modes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        for (mode in modes) {
            curTime += RatingState.BLOCK_INTERVAL + 100.0
            state.add(Rating(mode = mode.value, time = curTime, score = 3))
        }

        for (mode in modes) {
            assertTrue(state.isIntroduced(mode))
        }

        // Fail SPEAK only after block expires
        curTime += RatingState.BLOCK_INTERVAL + 1000.0
        state.add(Rating(mode = "speak", time = curTime, score = 1))

        // When unblocked, SPEAK urgency should be 1.0 (last was red)
        val futureT = curTime + RatingState.RED_BLOCK_INTERVAL + 1000.0
        assertEquals(1.0, state.urgency(Mode.SPEAK, futureT), 1e-6)

        // LISTEN should still have normal tanh urgency (< 1.0 and >= -1.0)
        val listenU = state.urgency(Mode.LISTEN, futureT)
        assertTrue(listenU < 1.0)
        assertTrue(listenU >= -1.0)
    }

    // ==========================================
    // 2. DECKENGINE LOOKAHEAD & SCORING ADVERSARIAL TESTS
    // ==========================================

    @Test(expected = IllegalStateException::class)
    fun testEmptyDeckThrowsOnChooseTask() {
        val emptyDeck = DeckEngine(
            targetLanguageCode = "empty",
            nativeLanguageCode = "english",
            unitsWithCards = emptyList(),
            cardsByUnitId = emptyMap()
        )
        emptyDeck.chooseTask(100.0)
    }

    @Test(expected = IllegalStateException::class)
    fun testEmptyCardsThrowsOnDraw() {
        val units = listOf(WordUnit("unit_0", Difficulty.A1))
        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = emptyMap()
        )
        deck.draw(100.0)
    }

    @Test
    fun testUnitWithNoCardsFallbackDraw() {
        val unit0 = WordUnit("unit_0", Difficulty.A1)
        val unit1 = WordUnit("unit_1", Difficulty.A1)
        val card1 = Card(
            id = "c1",
            sentence = "sentence 1",
            native_sentence = "sentence native 1",
            audio_filename = "a1.ogg",
            slow_audio_filename = "s1.ogg",
            native_audio_filename = "n1.ogg",
            unit_tags = listOf(UnitTag("unit_1", "unit_1"))
        )

        // unitsWithCards contains only units with cards (unit1)
        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = listOf(unit1),
            cardsByUnitId = mapOf("unit_1" to listOf(card1)),
            unitLookup = mapOf("unit_0" to unit0, "unit_1" to unit1)
        )

        val (_, drawnCard) = deck.draw(100.0)
        assertEquals("c1", drawnCard.id)
    }

    @Test
    fun testHeavyUsageCardScoringDecay() {
        val unit = WordUnit("u1", Difficulty.A1)
        val card = Card(
            id = "c1",
            sentence = "s",
            native_sentence = "sn",
            audio_filename = "a.ogg",
            slow_audio_filename = "s.ogg",
            native_audio_filename = "n.ogg",
            unit_tags = listOf(UnitTag("u1", "u1"))
        )

        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = listOf(unit),
            cardsByUnitId = mapOf("u1" to listOf(card)),
            unitLookup = mapOf("u1" to unit)
        )

        val tNow = 100_000.0
        // Log 100 usages over 50 days
        for (i in 0 until 100) {
            val tUse = tNow - (i * 0.5 * DAY)
            deck.logUsage("c1", isReported = false, currentTime = tUse)
        }

        val score = deck.scoreCard(card, Mode.LISTEN, tNow)
        assertFalse(score.isNaN())
        assertFalse(score.isInfinite())
        // Score should be heavily negative due to 100 usages
        assertTrue(score < -1000.0)
    }

    @Test
    fun testReportedErrorMassivePenalty() {
        val unit = WordUnit("u1", Difficulty.A1)
        val normalCard = Card(
            id = "normal_card",
            sentence = "normal",
            native_sentence = "normal native",
            audio_filename = "a.ogg",
            slow_audio_filename = "s.ogg",
            native_audio_filename = "n.ogg",
            unit_tags = listOf(UnitTag("u1", "u1"))
        )
        val reportedCard = Card(
            id = "reported_card",
            sentence = "reported",
            native_sentence = "reported native",
            audio_filename = "a.ogg",
            slow_audio_filename = "s.ogg",
            native_audio_filename = "n.ogg",
            unit_tags = listOf(UnitTag("u1", "u1"))
        )

        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = listOf(unit),
            cardsByUnitId = mapOf("u1" to listOf(normalCard, reportedCard)),
            unitLookup = mapOf("u1" to unit)
        )

        // Log reported error on reportedCard
        deck.logUsage("reported_card", isReported = true, currentTime = 100.0)
        // Log normal usage on normalCard
        deck.logUsage("normal_card", isReported = false, currentTime = 100.0)

        val scoreReported = deck.scoreCard(reportedCard, Mode.LISTEN, 100.0)
        val scoreNormal = deck.scoreCard(normalCard, Mode.LISTEN, 100.0)

        // Difference must be at least REPORT_PENALTY (1,000,000.0)
        assertTrue(scoreNormal - scoreReported >= DeckEngine.REPORT_PENALTY - 1.0)

        // Draw must pick normalCard
        val (_, drawn) = deck.draw(100.0)
        assertEquals("normal_card", drawn.id)
    }

    @Test
    fun testLookaheadToleranceWindowAndPressureThreshold() {
        val units = (0 until 20).map { WordUnit("u_$it", Difficulty.A1) }
        val cardsByUnit = units.associate { u ->
            u.id() to listOf(
                Card(
                    id = "c_${u.id()}",
                    sentence = u.id(),
                    native_sentence = "nat ${u.id()}",
                    audio_filename = "a.ogg",
                    slow_audio_filename = "s.ogg",
                    native_audio_filename = "n.ogg",
                    unit_tags = listOf(UnitTag(u.id(), u.id()))
                )
            )
        }

        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = cardsByUnit,
            unitLookup = units.associateBy { it.id() }
        )
        // Use all 4 modes so pressure can accumulate to 4 * 5.0 = 20.0 > 10.0
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        deck.setModes(allModes)

        // Rate unit 0 with Green across all modes at t=0
        for (m in allModes) {
            deck.rate(units[0], m, 3, currentTime = 0.0)
        }

        // Unit 1 is unintroduced (intro_index = 1).
        // Tolerance = max((1 * 1.0 + 10.0).toInt(), 1) = 11.
        // Rate unit 5 (inside window) with Red at t=10.0, Green after red block at t=700.0
        deck.rate(units[5], Mode.LISTEN, 1, currentTime = 10.0)
        deck.rate(units[5], Mode.LISTEN, 3, currentTime = 700.0)

        // At t = 800.0, unit 5 is blocked by green rating (20h block).
        // Moderate pressure (<= INTRODUCTION_THRESHOLD 10.0), deck introduces unit 1.
        val (_, taskUnit1) = deck.chooseTask(800.0)
        assertEquals("u_1", taskUnit1)

        // Now create massive pressure (> 10.0) by properly introducing and failing 10 units in all 4 modes
        for (i in 2..11) {
            for (m in allModes) {
                deck.rate(units[i], m, 1, currentTime = 0.0)
                deck.rate(units[i], m, 3, currentTime = 700.0)
                deck.rate(units[i], m, 1, currentTime = 700.0 + RatingState.BLOCK_INTERVAL + 10.0)
            }
        }

        // At t = 200_000.0, all these failed units have urgency = 1.0 across 4 modes.
        // Total pressure > 10.0 -> DeckEngine should pick highest pressure unit instead of introducing u_1!
        val (_, taskUnitPressure) = deck.chooseTask(200_000.0)
        assertNotEquals("u_1", taskUnitPressure)
        assertTrue(taskUnitPressure.startsWith("u_"))
    }

    @Test
    fun testUntouchedAndUnintroducedPenalties() {
        val uUntouched = WordUnit("u_untouched", Difficulty.A1)
        val uUnintroduced = WordUnit("u_unintro", Difficulty.A1)
        val uIntroduced = WordUnit("u_intro", Difficulty.A1)

        val card = Card(
            id = "c_multi",
            sentence = "multi unit sentence",
            native_sentence = "multi",
            audio_filename = "a.ogg",
            slow_audio_filename = "s.ogg",
            native_audio_filename = "n.ogg",
            unit_tags = listOf(
                UnitTag("u_untouched", "u_untouched"),
                UnitTag("u_unintro", "u_unintro"),
                UnitTag("u_intro", "u_intro")
            )
        )

        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = listOf(uUntouched, uUnintroduced, uIntroduced),
            cardsByUnitId = mapOf("u_intro" to listOf(card)),
            unitLookup = mapOf(
                "u_untouched" to uUntouched,
                "u_unintro" to uUnintroduced,
                "u_intro" to uIntroduced
            )
        )

        // u_unintro: touched=true, introduced=false
        deck.rate(uUnintroduced, Mode.SPEAK, 1, currentTime = 100.0)

        // u_intro: touched=true, introduced=true (rate score 3 on LISTEN)
        deck.rate(uIntroduced, Mode.LISTEN, 3, currentTime = 100.0)

        // Score card on Mode.LISTEN at t=100.0:
        // u_untouched: touched=false -> -200.0
        // u_unintro: touched=true, introduced(LISTEN)=false -> -100.0
        // u_intro: touched=true, introduced(LISTEN)=true -> 0 penalty
        // Matching difficulty bonuses: 3 * 0.1 = +0.3
        // Total expected: -200 - 100 + 0.3 = -299.7
        val score = deck.scoreCard(card, Mode.LISTEN, 100.0)
        assertEquals(-299.7, score, 1e-3)
    }

    @Test
    fun testDifficultyMatchingAndPenalties() {
        val uA1 = WordUnit("u_a1", Difficulty.A1)
        val uB1 = WordUnit("u_b1", Difficulty.B1)
        val uC1 = WordUnit("u_c1", Difficulty.C1)

        val card = Card(
            id = "c_diff",
            sentence = "diff",
            native_sentence = "diff native",
            audio_filename = "a.ogg",
            slow_audio_filename = "s.ogg",
            native_audio_filename = "n.ogg",
            unit_tags = listOf(
                UnitTag("u_a1", "u_a1"),
                UnitTag("u_b1", "u_b1"),
                UnitTag("u_c1", "u_c1")
            )
        )

        val deck = DeckEngine(
            targetLanguageCode = "test",
            nativeLanguageCode = "english",
            unitsWithCards = listOf(uA1, uB1, uC1),
            cardsByUnitId = mapOf("u_b1" to listOf(card)),
            unitLookup = mapOf(
                "u_a1" to uA1,
                "u_b1" to uB1,
                "u_c1" to uC1
            )
        )
        // Mark all as introduced
        deck.rate(uA1, Mode.LISTEN, 3, currentTime = 100.0)
        deck.rate(uB1, Mode.LISTEN, 3, currentTime = 100.0)
        deck.rate(uC1, Mode.LISTEN, 3, currentTime = 100.0)

        // Set deck target difficulty to B1
        deck.setDifficulty(Difficulty.B1)

        // Score card:
        // u_a1 (A1 < B1): no diff bonus
        // u_b1 (B1 == B1): +0.1 match bonus
        // u_c1 (C1 > B1): +0.1 difficulty penalty
        // Score = 0.1 + 0.1 = 0.2
        val score = deck.scoreCard(card, Mode.LISTEN, 100.0)
        assertEquals(0.2, score, 1e-3)
    }

    @Test
    fun testMassiveStateSerializationRoundtrip() {
        val diffValues = Difficulty.values()
        val units = (0 until 50).map { WordUnit("unit_$it", diffValues[it % diffValues.size]) }
        val cards = units.map { u ->
            Card(
                id = "card_${u.id()}",
                sentence = "Sentence for ${u.id()}",
                native_sentence = "Native for ${u.id()}",
                audio_filename = "a.ogg",
                slow_audio_filename = "s.ogg",
                native_audio_filename = "n.ogg",
                unit_tags = listOf(UnitTag(u.id(), u.id()))
            )
        }
        val cardsByUnitId = units.associate { it.id() to listOf(cards.first { c -> c.id == "card_${it.id()}" }) }

        val deck = DeckEngine(
            targetLanguageCode = "stress_lang",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = cardsByUnitId,
            translations = units.associate { it.id() to "Trans ${it.id()}" },
            unitLookup = units.associateBy { it.id() }
        )
        deck.setDifficulty(Difficulty.C1)
        deck.setAssumeKnown(Difficulty.B1)

        // Add 500 ratings across units
        var t = 10_000.0
        val modes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        for (i in 0 until 500) {
            t += 60.0
            val unit = units[i % units.size]
            val mode = modes[i % modes.size]
            val score = i % 4
            deck.rate(unit, mode, score, currentTime = t)
        }

        // Add 200 card usages
        for (i in 0 until 200) {
            t += 10.0
            val card = cards[i % cards.size]
            deck.logUsage(card.id, isReported = (i % 10 == 0), currentTime = t)
        }

        val json = deck.saveJson()
        assertNotNull(json)
        assertTrue(json.length > 1000)

        // Restore into new DeckEngine
        val restoredDeck = DeckEngine(
            targetLanguageCode = "stress_lang",
            nativeLanguageCode = "english",
            unitsWithCards = units,
            cardsByUnitId = cardsByUnitId,
            translations = units.associate { it.id() to "Trans ${it.id()}" },
            unitLookup = units.associateBy { it.id() }
        )
        restoredDeck.loadJson(json)

        assertEquals(deck.getDifficulty(), restoredDeck.getDifficulty())
        assertEquals(deck.getAssumeKnown(), restoredDeck.getAssumeKnown())
        assertEquals(deck.getRatingStates().size, restoredDeck.getRatingStates().size)
        assertEquals(deck.getCardUsages().size, restoredDeck.getCardUsages().size)

        // Compare stats
        val stats1 = deck.stats(t + 1000.0)
        val stats2 = restoredDeck.stats(t + 1000.0)
        assertEquals(stats1.waiting, stats2.waiting)
        assertEquals(stats1.known, stats2.known)
        assertEquals(stats1.mature, stats2.mature)

        // Compare draw result
        val (m1, c1) = deck.draw(t + 1000.0)
        val (m2, c2) = restoredDeck.draw(t + 1000.0)
        assertEquals(m1, m2)
        assertEquals(c1.id, c2.id)
    }
}
