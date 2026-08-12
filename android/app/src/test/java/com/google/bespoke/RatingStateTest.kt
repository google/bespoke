package com.google.bespoke

import com.google.bespoke.model.Mode
import com.google.bespoke.model.Rating
import com.google.bespoke.srs.RatingState
import org.junit.Assert.*
import org.junit.Test

class RatingStateTest {

    companion object {
        const val DAY = 24.0 * 60.0 * 60.0
    }

    @Test
    fun testPositiveUrgency() {
        val state = RatingState()
        state.add(Rating(mode = "listen", time = DAY * 0, score = 1))
        state.add(Rating(mode = "listen", time = DAY * 1, score = 3))
        state.add(Rating(mode = "listen", time = DAY * 2, score = 1))
        assertEquals(1.0, state.urgency(Mode.LISTEN, DAY * 3), 1e-6)
        state.add(Rating(mode = "listen", time = DAY * 3 + 1, score = 3))
        assertTrue(state.urgency(Mode.LISTEN, DAY * 10) > 0.0)
    }

    @Test
    fun testNegativeUrgency() {
        val state = RatingState()
        state.add(Rating(mode = "listen", time = DAY * 0, score = 1))
        state.add(Rating(mode = "listen", time = DAY * 1, score = 3))
        assertTrue(state.urgency(Mode.LISTEN, DAY * 2) < 0.0)
    }

    @Test
    fun testCannotBlockPositiveUrgency() {
        val state = RatingState()
        state.add(Rating(mode = "write", time = DAY * 0, score = 1))
        state.add(Rating(mode = "write", time = DAY * 1, score = 3))
        state.add(Rating(mode = "write", time = DAY * 2 - 1, score = 0))
        state.add(Rating(mode = "write", time = DAY * 2, score = 1))
        assertEquals(1.0, state.urgency(Mode.WRITE, DAY * 3), 1e-6)
    }

    @Test
    fun testBlockedNegativeUrgency() {
        val state = RatingState()
        state.add(Rating(mode = "write", time = DAY * 0, score = 1))
        state.add(Rating(mode = "write", time = DAY * 1, score = 3))
        state.add(Rating(mode = "write", time = DAY * 2, score = 1))
        state.add(Rating(mode = "write", time = DAY * 3 - 1, score = 0))
        state.add(Rating(mode = "write", time = DAY * 3, score = 3))
        assertTrue(state.urgency(Mode.WRITE, DAY * 4) > 0.0)
    }

    @Test
    fun testGreenIntroductionUrgency() {
        val state = RatingState()
        state.add(Rating(mode = "listen", time = DAY * 0, score = 3))
        assertTrue(state.urgency(Mode.LISTEN, DAY * 21) < 0.0)
        state.add(Rating(mode = "speak", time = DAY * 1, score = 3))
        assertTrue(state.urgency(Mode.SPEAK, DAY * 21) < 0.0)
        state.add(Rating(mode = "speak", time = DAY * 2, score = 1))
        state.add(Rating(mode = "read", time = DAY * 3, score = 3))
        assertTrue(state.urgency(Mode.READ, DAY * 21) > 0.0)
        assertTrue(state.urgency(Mode.READ, DAY * 3 + 60.0 * 60.0) < 0.0)
    }

    @Test
    fun testGetRatingsCopy() {
        val rating1 = Rating(mode = "listen", time = DAY * 0, score = 3)
        val state = RatingState(listOf(rating1))
        val rating2 = Rating(mode = "speak", time = DAY * 1, score = 0)
        state.add(rating2)
        val ratings = state.ratings()
        assertEquals(2, ratings.size)
        assertEquals("listen", ratings[0].mode)
        assertEquals("speak", ratings[1].mode)
        state.add(rating2)
        assertEquals(2, ratings.size)
    }

    @Test
    fun testIsTouched() {
        val state = RatingState()
        assertFalse(state.isTouched())
        state.add(Rating(mode = "read", time = DAY * 0, score = 0))
        assertFalse(state.isTouched())
        state.add(Rating(mode = "read", time = DAY * 1, score = 1))
        assertTrue(state.isTouched())
        state.add(Rating(mode = "read", time = DAY * 2, score = 0))
        assertTrue(state.isTouched())
    }

    @Test
    fun testIsIntroduced() {
        val state = RatingState()
        assertFalse(state.isIntroduced(Mode.LISTEN))
        assertFalse(state.isIntroduced(Mode.SPEAK))
        state.add(Rating(mode = "listen", time = DAY * 0, score = 0))
        assertFalse(state.isIntroduced(Mode.LISTEN))
        assertFalse(state.isIntroduced(Mode.SPEAK))
        state.add(Rating(mode = "read", time = DAY * 1, score = 3))
        assertFalse(state.isIntroduced(Mode.LISTEN))
        assertFalse(state.isIntroduced(Mode.SPEAK))
        state.add(Rating(mode = "speak", time = DAY * 2, score = 1))
        assertFalse(state.isIntroduced(Mode.LISTEN))
        assertFalse(state.isIntroduced(Mode.SPEAK))
        state.add(Rating(mode = "listen", time = DAY * 3, score = 3))
        assertTrue(state.isIntroduced(Mode.LISTEN))
        assertFalse(state.isIntroduced(Mode.SPEAK))
        state.add(Rating(mode = "speak", time = DAY * 4, score = 3))
        assertTrue(state.isIntroduced(Mode.LISTEN))
        assertTrue(state.isIntroduced(Mode.SPEAK))
    }

    @Test
    fun testIsWaiting() {
        val state = RatingState()
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        assertFalse(state.isWaiting(allModes, DAY * 0))
        state.add(Rating(mode = "listen", time = DAY * 1, score = 1))
        assertFalse(state.isWaiting(allModes, DAY * 1))
        state.add(Rating(mode = "listen", time = DAY * 2, score = 3))
        assertFalse(state.isWaiting(allModes, DAY * 2))
        assertFalse(state.isWaiting(allModes, DAY * 3))
        assertTrue(state.isWaiting(allModes, DAY * 10))
    }

    @Test
    fun testIsWaitingWrongMode() {
        val state = RatingState()
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        state.add(Rating(mode = "listen", time = DAY * 1, score = 1))
        state.add(Rating(mode = "listen", time = DAY * 2, score = 3))
        assertTrue(state.isWaiting(allModes, DAY * 10))
        assertFalse(state.isWaiting(listOf(Mode.SPEAK), DAY * 10))
    }

    @Test
    fun testCanBeIntroduced() {
        val state = RatingState()
        val allModes = listOf(Mode.LISTEN, Mode.SPEAK, Mode.READ, Mode.WRITE)
        assertTrue(state.canBeIntroduced(allModes, DAY * 0))
        state.add(Rating(mode = "listen", time = DAY * 0, score = 0))
        assertFalse(state.canBeIntroduced(allModes, DAY * 0 + 1))
        assertTrue(state.canBeIntroduced(allModes, DAY * 2))
        state.add(Rating(mode = "listen", time = DAY * 2, score = 3))
        assertTrue(state.canBeIntroduced(allModes, DAY * 3))
        state.add(Rating(mode = "speak", time = DAY * 3, score = 3))
        assertTrue(state.canBeIntroduced(allModes, DAY * 4))
        assertFalse(state.canBeIntroduced(listOf(Mode.LISTEN, Mode.SPEAK), DAY * 4))
    }

    @Test
    fun testStats() {
        val state = RatingState()
        assertFalse(state.isKnown(Mode.READ))
        assertFalse(state.isMature(Mode.READ))
        state.add(Rating(mode = "read", time = DAY * 1, score = 3))
        assertTrue(state.isKnown(Mode.READ))
        assertFalse(state.isMature(Mode.READ))
        state.add(Rating(mode = "read", time = DAY * 30, score = 3))
        assertTrue(state.isKnown(Mode.READ))
        assertTrue(state.isMature(Mode.READ))
        assertFalse(state.isKnown(Mode.WRITE))
        assertFalse(state.isMature(Mode.WRITE))
    }
}
