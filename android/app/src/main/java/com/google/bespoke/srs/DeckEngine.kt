package com.google.bespoke.srs

import com.google.bespoke.model.*
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.reflect.TypeToken
import java.io.File
import kotlin.math.exp
import kotlin.math.max

class DeckEngine(
    val targetLanguageCode: String,
    val nativeLanguageCode: String,
    val unitsWithCards: List<UnitItem>,
    val cardsByUnitId: Map<String, List<Card>> = emptyMap(),
    val translations: Map<String, String> = emptyMap(),
    val unitLookup: Map<String, UnitItem> = emptyMap(),
    val cardProvider: ((unitId: String, limit: Int) -> List<Card>)? = null
) {
    companion object {
        const val TOUCH_TOLERANCE_FACTOR = 1.0
        const val TOUCH_TOLERANCE_BUFFER = 10.0
        const val INTRODUCTION_THRESHOLD = 10.0
        const val INTRODUCE_OUT_OF_ORDER = false

        const val REPORT_PENALTY = 1000000.0
        const val CARD_USAGE_FACTOR = 1000.0
        const val CARD_USAGE_DECAY = 0.1
        const val UNTOUCHED_PENALTY = 200.0
        const val UNINTRODUCED_PENALTY = 100.0
        const val URGENCY_BONUS = 10.0
        const val DIFFICULTY_MATCH_BONUS = 0.1
        const val DIFFICULTY_PENALTY = 0.1
    }

    private val lock = Any()
    private val ratingStates = mutableMapOf<String, RatingState>()
    private val cardIdUses = mutableMapOf<String, MutableList<CardUsage>>()
    private var difficulty = Difficulty.A1
    private var modes = listOf(Mode.LISTEN, Mode.SPEAK)
    private var assumeKnown: Difficulty? = null
    private var knownUnitModes = 0
    private var matureUnitModes = 0

    fun translatedUnit(unitId: String): String {
        translations[unitId]?.let { if (it.isNotEmpty()) return it }
        val unit = unitLookup[unitId]
        if (unit is DictionaryUnit && unit.definition().isNotEmpty()) {
            return unit.definition()
        }
        return ""
    }

    fun chooseTask(currentTime: Double): Pair<Mode, String> {
        val defaultState = RatingState()

        var maxUrgency = -1e5
        var maxMode: Mode? = null
        var maxUnitId: String? = null
        var introductionIndex = 0
        var introductionMode: Mode? = null
        var introductionUnitId: String? = null
        var introductionIsTouched = false

        for ((i, unit) in unitsWithCards.withIndex()) {
            val state = ratingStates[unit.id()] ?: defaultState
            val isSkipped = assumeKnown != null && unit.difficulty().ordinal <= assumeKnown!!.ordinal
            for (mode in modes) {
                val urgency = state.urgency(mode, currentTime)
                if (urgency > maxUrgency) {
                    maxUrgency = urgency
                    maxMode = mode
                    maxUnitId = unit.id()
                }
                if (!isSkipped && urgency >= 0.0 && !state.isIntroduced(mode)) {
                    introductionIndex = i
                    introductionMode = mode
                    introductionUnitId = unit.id()
                    introductionIsTouched = state.isTouched()
                    break
                }
            }
            if (introductionMode != null) break
        }

        if (maxMode == null || maxUnitId == null) {
            throw IllegalStateException("No units found")
        }

        if (maxUrgency > 0.0) {
            return Pair(maxMode, maxUnitId)
        }
        if (introductionMode == null || introductionUnitId == null) {
            return Pair(maxMode, maxUnitId)
        }

        val tolerance = max((introductionIndex * TOUCH_TOLERANCE_FACTOR + TOUCH_TOLERANCE_BUFFER).toInt(), 1)
        val toleranceIndex = minOf(introductionIndex + tolerance, unitsWithCards.size)
        var totalPressure = 0.0
        var maxPressure = 0.0
        var maxPressureMode: Mode? = null
        var maxPressureUnitId: String? = null

        for (j in 0 until toleranceIndex) {
            val unit = unitsWithCards[j]
            val state = ratingStates[unit.id()] ?: defaultState
            for (mode in modes) {
                val urgency = state.urgency(mode, currentTime)
                val pressure = max(urgency, 0.0)
                if (pressure > maxPressure) {
                    maxPressure = pressure
                    maxPressureMode = mode
                    maxPressureUnitId = unit.id()
                }
                totalPressure += pressure
            }
        }

        if (totalPressure > INTRODUCTION_THRESHOLD) {
            if (INTRODUCE_OUT_OF_ORDER && !introductionIsTouched) {
                for (j in 0 until toleranceIndex) {
                    val unit = unitsWithCards[j]
                    val state = ratingStates[unit.id()] ?: defaultState
                    if (!state.isIntroduced(introductionMode) && state.isTouched()) {
                        return Pair(introductionMode, unit.id())
                    }
                }
            }
            return Pair(maxPressureMode ?: maxMode, maxPressureUnitId ?: maxUnitId)
        } else {
            return Pair(introductionMode, introductionUnitId)
        }
    }

    fun scoreCard(card: Card, mode: Mode, currentTime: Double): Double {
        val defaultState = RatingState()
        var score = 0.0
        val usages = cardIdUses[card.id] ?: emptyList()
        for (usage in usages) {
            if (usage.is_reported) {
                score -= REPORT_PENALTY
            }
            val days = (currentTime - usage.time) / (60.0 * 60.0 * 24.0)
            if (days >= 0.0) {
                score -= CARD_USAGE_FACTOR * exp(-CARD_USAGE_DECAY * days)
            }
        }

        for (unitId in card.unitIds()) {
            val state = ratingStates[unitId] ?: defaultState
            if (!state.isTouched()) {
                score -= UNTOUCHED_PENALTY
            } else if (!state.isIntroduced(mode)) {
                score -= UNINTRODUCED_PENALTY
            }
            val urgency = state.urgency(mode, currentTime)
            if (urgency > 0.0) {
                score += URGENCY_BONUS * max(urgency, 0.1)
            }
            val unit = unitLookup[unitId] ?: unitsWithCards.firstOrNull { it.id() == unitId }
            val unitDiff = unit?.difficulty() ?: Difficulty.A1
            if (unitDiff == difficulty) {
                score += DIFFICULTY_MATCH_BONUS
            } else if (unitDiff.ordinal > difficulty.ordinal) {
                score += DIFFICULTY_PENALTY
            }
        }
        return score
    }

    private fun getCardsForUnit(unitId: String, limit: Int = 1000): List<Card> {
        return if (cardProvider != null) {
            cardProvider.invoke(unitId, limit)
        } else {
            cardsByUnitId[unitId] ?: emptyList()
        }
    }

    fun draw(currentTime: Double = System.currentTimeMillis() / 1000.0): Pair<Mode, Card> {
        val (mode, unitId) = chooseTask(currentTime)
        val candidateCards = getCardsForUnit(unitId, 1000)
        val cardsToScore = if (candidateCards.isEmpty()) {
            rate(unitLookup[unitId] ?: WordUnit(unitId, Difficulty.A1), mode, 0, currentTime)
            val randomUnit = unitsWithCards.randomOrNull()
            if (randomUnit != null) {
                getCardsForUnit(randomUnit.id(), 1000)
            } else {
                emptyList()
            }
        } else {
            candidateCards
        }
        val bestCard = cardsToScore.maxByOrNull { scoreCard(it, mode, currentTime) }
            ?: throw IllegalStateException("No cards found to draw")
        return Pair(mode, bestCard)
    }

    fun rate(
        unit: UnitItem,
        mode: Mode,
        score: Int,
        currentTime: Double = System.currentTimeMillis() / 1000.0
    ) {
        synchronized(lock) {
            val rating = Rating(mode.value, currentTime, score)
            val state = ratingStates.getOrPut(unit.id()) { RatingState() }
            if (modes.contains(mode)) {
                if (state.isKnown(mode)) knownUnitModes--
                if (state.isMature(mode)) matureUnitModes--
            }
            state.add(rating)
            if (modes.contains(mode)) {
                if (state.isKnown(mode)) knownUnitModes++
                if (state.isMature(mode)) matureUnitModes++
            }
        }
    }

    fun logUsage(
        cardId: String,
        isReported: Boolean = false,
        currentTime: Double = System.currentTimeMillis() / 1000.0
    ) {
        synchronized(lock) {
            val list = cardIdUses.getOrPut(cardId) { mutableListOf() }
            list.add(CardUsage(currentTime, isReported))
        }
    }

    fun setDifficulty(d: Difficulty) {
        synchronized(lock) { difficulty = d }
    }

    fun getDifficulty(): Difficulty = difficulty

    fun setModes(m: List<Mode>) {
        synchronized(lock) {
            modes = m
            knownUnitModes = 0
            matureUnitModes = 0
            for (state in ratingStates.values) {
                for (mode in modes) {
                    if (state.isKnown(mode)) knownUnitModes++
                    if (state.isMature(mode)) matureUnitModes++
                }
            }
        }
    }

    fun getModes(): List<Mode> = modes

    fun setAssumeKnown(d: Difficulty?) {
        synchronized(lock) { assumeKnown = d }
    }

    fun getAssumeKnown(): Difficulty? = assumeKnown

    fun stats(currentTime: Double = System.currentTimeMillis() / 1000.0): DeckStats {
        var waiting = 0
        for (unit in unitsWithCards) {
            val state = ratingStates[unit.id()]
            val isSkipped = assumeKnown != null && unit.difficulty().ordinal <= assumeKnown!!.ordinal
            if (state == null) {
                if (!isSkipped) break
                continue
            }
            if (state.isWaiting(modes, currentTime)) {
                waiting++
            }
            if (!isSkipped && state.canBeIntroduced(modes, currentTime)) {
                break
            }
        }
        return DeckStats(
            waiting = waiting,
            known = if (modes.isNotEmpty()) knownUnitModes / modes.size else 0,
            mature = if (modes.isNotEmpty()) matureUnitModes / modes.size else 0
        )
    }

    fun getRatingStates(): Map<String, RatingState> = ratingStates

    fun getCardUsages(): Map<String, List<CardUsage>> = cardIdUses

    fun saveJson(): String {
        synchronized(lock) {
            val ratingsMap = mutableMapOf<String, List<Rating>>()
            for ((key, state) in ratingStates) {
                ratingsMap[key] = state.ratings()
            }
            val data = mutableMapOf<String, Any>(
                "target_language" to targetLanguageCode,
                "native_language" to nativeLanguageCode,
                "ratings" to ratingsMap,
                "card_id_uses" to cardIdUses,
                "difficulty" to difficulty.value,
                "modes" to modes.map { it.value }
            )
            assumeKnown?.let {
                data["assume_known"] = it.value
            }
            return GsonBuilder().setPrettyPrinting().create().toJson(data)
        }
    }

    fun save(file: File) {
        val json = saveJson()
        file.writeText(json, Charsets.UTF_8)
    }

    fun loadJson(jsonString: String) {
        synchronized(lock) {
            val gson = Gson()
            val type = object : TypeToken<Map<String, Any>>() {}.type
            val data: Map<String, Any> = gson.fromJson(jsonString, type)

            ratingStates.clear()
            val ratingsRaw = data["ratings"] as? Map<*, *> ?: emptyMap<String, Any>()
            for ((unitIdKey, ratingsListRaw) in ratingsRaw) {
                val listJson = gson.toJson(ratingsListRaw)
                val ratingsListType = object : TypeToken<List<Rating>>() {}.type
                val ratingsList: List<Rating> = gson.fromJson(listJson, ratingsListType) ?: emptyList()
                ratingStates[unitIdKey.toString()] = RatingState(ratingsList)
            }

            cardIdUses.clear()
            val usagesRaw = data["card_id_uses"] as? Map<*, *> ?: emptyMap<String, Any>()
            for ((cardIdKey, usageListRaw) in usagesRaw) {
                val listJson = gson.toJson(usageListRaw)
                val usagesListType = object : TypeToken<List<CardUsage>>() {}.type
                val usagesList: List<CardUsage> = gson.fromJson(listJson, usagesListType) ?: emptyList()
                cardIdUses[cardIdKey.toString()] = usagesList.toMutableList()
            }

            val diffStr = data["difficulty"] as? String
            if (diffStr != null) {
                difficulty = Difficulty.fromValue(diffStr)
            }

            val modesRaw = data["modes"] as? List<*>
            if (modesRaw != null) {
                modes = modesRaw.map { Mode.fromValue(it.toString()) }
            }

            val assumeStr = data["assume_known"] as? String
            assumeKnown = if (assumeStr != null) Difficulty.fromValue(assumeStr) else null

            // Recompute stats
            knownUnitModes = 0
            matureUnitModes = 0
            for (state in ratingStates.values) {
                for (mode in modes) {
                    if (state.isKnown(mode)) knownUnitModes++
                    if (state.isMature(mode)) matureUnitModes++
                }
            }
        }
    }

    fun load(file: File) {
        if (file.exists()) {
            val text = file.readText(Charsets.UTF_8)
            loadJson(text)
        }
    }
}
