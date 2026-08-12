package com.google.bespoke.srs

import com.google.bespoke.model.Mode
import com.google.bespoke.model.Rating
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.tanh

class RatingState(initialRatings: List<Rating> = emptyList()) {
    companion object {
        const val MINUTE = 60.0
        const val HOUR = MINUTE * 60.0
        const val DAY = HOUR * 24.0

        const val BLOCK_INTERVAL = HOUR * 20.0
        const val RED_BLOCK_INTERVAL = MINUTE * 10.0
        const val MINIMUM_BLOCK_INTERVAL = MINUTE * 1.0
        const val BLOCK_SCALE_INTERVAL = DAY * 1.0
        const val INTERVAL_DECAY = 0.5
        const val INTERVAL_FACTOR = 1.8
        const val MODE_INITIAL_GREEN_INTERVAL = HOUR * 1.0
        const val FULL_INITIAL_GREEN_INTERVAL = DAY * 14.0
        const val WAITING_PROJECTION = RED_BLOCK_INTERVAL
        const val KNOWN_AGE = DAY * 1.0
        const val MATURE_AGE = DAY * 21.0
    }

    private val _ratings = mutableListOf<Rating>()
    private val _lastRed = mutableMapOf<Mode, Double>()
    private val _greenStart = mutableMapOf<Mode, Double>()
    private val _greenEnd = mutableMapOf<Mode, Double>()
    private val _greenStreak = mutableMapOf<Mode, Double>()
    private var _blockEnd: Double = -1e5
    private var _isTouched: Boolean = false

    init {
        for (rating in initialRatings) {
            add(rating)
        }
    }

    fun add(rating: Rating) {
        if (_ratings.isNotEmpty() && _ratings.last().time > rating.time) {
            // Reject out of order rating
            return
        }
        _ratings.add(rating)
        val mode = rating.modeEnum
        val baseBlockInterval: Double = when (rating.score) {
            0 -> BLOCK_INTERVAL
            1, 2 -> {
                _lastRed[mode] = rating.time
                _greenStart.remove(mode)
                _greenEnd.remove(mode)
                val greenStreak = _greenStreak[mode]
                if (greenStreak != null) {
                    _greenStreak[mode] = greenStreak * INTERVAL_DECAY
                }
                _isTouched = true
                RED_BLOCK_INTERVAL
            }
            3 -> {
                if (rating.time > _blockEnd) {
                    val lastRedTime = _lastRed[mode]
                    var streak: Double = when {
                        lastRedTime != null -> rating.time - lastRedTime
                        _lastRed.isNotEmpty() -> MODE_INITIAL_GREEN_INTERVAL
                        else -> FULL_INITIAL_GREEN_INTERVAL
                    }

                    val greenStart = _greenStart[mode]
                    if (greenStart == null) {
                        _greenStart[mode] = rating.time
                    } else {
                        streak = max(streak, rating.time - greenStart)
                    }

                    val lastStreak = _greenStreak[mode] ?: 0.0
                    _greenEnd[mode] = rating.time
                    _greenStreak[mode] = max(lastStreak, streak)
                }
                _isTouched = true
                BLOCK_INTERVAL
            }
            else -> 0.0
        }

        var maxGreenInterval = _greenStreak.values.maxOrNull() ?: 1.0
        if (maxGreenInterval <= 0.0) {
            maxGreenInterval = 1.0
        }
        val blockScale = 1.0 - exp(-maxGreenInterval / BLOCK_SCALE_INTERVAL)
        val blockInterval = max(baseBlockInterval * blockScale, MINIMUM_BLOCK_INTERVAL)
        _blockEnd = max(_blockEnd, rating.time + blockInterval)
    }

    fun ratings(): List<Rating> = _ratings.toList()

    fun urgency(mode: Mode, currentTime: Double): Double {
        if (currentTime < _blockEnd) {
            // Blocked
            return -1.0
        }
        val greenStreak = _greenStreak[mode] ?: return 0.0
        val greenEnd = _greenEnd[mode] ?: return 1.0
        val targetInterval = greenStreak * INTERVAL_FACTOR
        val target = greenEnd + targetInterval
        val deviation = (currentTime - target) / targetInterval
        return tanh(deviation)
    }

    fun isTouched(): Boolean = _isTouched

    fun isIntroduced(mode: Mode): Boolean = _greenStreak.containsKey(mode)

    fun isWaiting(modes: Iterable<Mode>, currentTime: Double): Boolean {
        val projectedTime = currentTime + WAITING_PROJECTION
        return modes.any { urgency(it, projectedTime) > 0.0 }
    }

    fun canBeIntroduced(modes: Iterable<Mode>, currentTime: Double): Boolean {
        if (currentTime < _blockEnd) return false
        return modes.any { !isIntroduced(it) }
    }

    fun isKnown(mode: Mode): Boolean = (_greenStreak[mode] ?: 0.0) > KNOWN_AGE

    fun isMature(mode: Mode): Boolean = (_greenStreak[mode] ?: 0.0) > MATURE_AGE
}
