package com.google.bespoke.srs

import com.google.bespoke.model.*
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonParser
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
        const val SOON_URGENT_INTERVAL = 10.0 * 60.0
        const val IMMEDIATE_URGENCY = 0.5
        const val SOON_URGENT_THRESHOLD = 10
        const val MIN_DRAW_PROBABILITY = 0.05
        const val MIN_DRAW_PROBABILITY_SELECTED = 0.2

        const val REPORT_PENALTY = 1000000.0
        const val CARD_USAGE_FACTOR = 1000.0
        const val CARD_USAGE_DECAY = 0.1
        const val BLOCKED_UNIT_PENALTY = 500.0
        const val UNTOUCHED_PENALTY = 200.0
        const val UNINTRODUCED_PENALTY = 100.0
        const val URGENCY_BONUS = 10.0
        const val DIFFICULTY_MATCH_BONUS = 0.1
        const val DIFFICULTY_PENALTY = 0.1
    }

    private val lock = Any()
    private val ratingStates = mutableMapOf<String, RatingState>()
    private val cardIdUses = mutableMapOf<String, MutableList<CardUsage>>()
    private val blockedUnits = mutableListOf<String>()
    private val blockedUnitsSet = mutableSetOf<String>()
    private var difficulty = Difficulty.A1
    private var modes = listOf(Mode.LISTEN, Mode.SPEAK)
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

    fun blockUnit(unitId: String) {
        synchronized(lock) {
            blockedUnits.remove(unitId)
            blockedUnits.add(unitId)
            blockedUnitsSet.add(unitId)
        }
    }

    fun unblockUnit(unitId: String) {
        synchronized(lock) {
            blockedUnits.remove(unitId)
            blockedUnitsSet.remove(unitId)
        }
    }

    fun isBlocked(unitId: String): Boolean {
        synchronized(lock) {
            return blockedUnitsSet.contains(unitId)
        }
    }

    fun blockedUnits(): List<String> {
        synchronized(lock) {
            return blockedUnits.reversed()
        }
    }

    fun chooseTask(currentTime: Double): Pair<Mode, String> {
        if (unitsWithCards.isEmpty()) {
            throw IllegalStateException("No units found")
        }
        val defaultState = RatingState()

        // Choose an urgent unit to learn
        var maxUrgency = -1e5
        var maxMode: Mode? = null
        var maxUnitId: String? = null
        var soonUrgent = 0
        val soonTime = currentTime + SOON_URGENT_INTERVAL
        val availableDifficulties = mutableListOf<Difficulty>()

        for (unit in unitsWithCards) {
            if (unit.difficulty().ordinal > difficulty.ordinal) {
                // Assumes units are sorted by difficulty
                break
            }
            if (blockedUnitsSet.contains(unit.id())) {
                continue
            }
            val state = ratingStates[unit.id()] ?: defaultState
            for (mode in modes) {
                if (!state.isIntroduced(mode)) {
                    if (!availableDifficulties.contains(unit.difficulty())) {
                        availableDifficulties.add(unit.difficulty())
                    }
                    continue
                }
                if (state.urgency(mode, soonTime) > 0.0) {
                    soonUrgent++
                    val urgency = state.urgency(mode, currentTime)
                    if (urgency > maxUrgency) {
                        maxUrgency = urgency
                        maxMode = mode
                        maxUnitId = unit.id()
                    }
                }
            }
        }

        if (maxUrgency > IMMEDIATE_URGENCY || soonUrgent >= SOON_URGENT_THRESHOLD) {
            if (maxMode != null && maxUnitId != null) {
                return Pair(maxMode, maxUnitId)
            }
        }

        // If nothing needs to be introduced, new difficulty unlocked
        if (availableDifficulties.isEmpty()) {
            difficulty = difficulty.saturatingIncrease()
            if (!availableDifficulties.contains(difficulty)) {
                availableDifficulties.add(difficulty)
            }
        }

        // Randomly choose a difficulty for introduction
        val firstGreens = mutableMapOf<Difficulty, Int>()
        val firstReds = mutableMapOf<Difficulty, Int>()
        for (d in availableDifficulties) {
            firstGreens[d] = 0
            firstReds[d] = 0
        }

        for (unit in unitsWithCards) {
            if (unit.difficulty().ordinal > difficulty.ordinal) {
                break
            }
            if (blockedUnitsSet.contains(unit.id())) {
                continue
            }
            if (!availableDifficulties.contains(unit.difficulty())) {
                continue
            }
            val state = ratingStates[unit.id()] ?: defaultState
            when (state.firstScore()) {
                1, 2 -> firstReds[unit.difficulty()] = (firstReds[unit.difficulty()] ?: 0) + 1
                3 -> firstGreens[unit.difficulty()] = (firstGreens[unit.difficulty()] ?: 0) + 1
            }
        }

        val probabilities = mutableMapOf<Difficulty, Double>()
        for (d in availableDifficulties) {
            val greens = firstGreens[d] ?: 0
            val reds = firstReds[d] ?: 0
            val ratio = if (greens + reds == 0) 0.0 else greens.toDouble() / (greens + reds)
            val minProb = if (d == difficulty) MIN_DRAW_PROBABILITY_SELECTED else MIN_DRAW_PROBABILITY
            probabilities[d] = 1.0 - ratio + ratio * minProb
        }

        val keys = probabilities.keys.toList()
        val weights = probabilities.values.toList()
        val totalWeight = weights.sum()
        val randomVal = Math.random() * totalWeight
        var cumulative = 0.0
        var chosen = keys.first()
        for (idx in keys.indices) {
            cumulative += weights[idx]
            if (randomVal <= cumulative) {
                chosen = keys[idx]
                break
            }
        }

        // Select the first half-introduced unit, or the first fresh one
        var chosenMode: Mode? = null
        var chosenUnitId: String? = null
        for (unit in unitsWithCards) {
            if (unit.difficulty().ordinal < chosen.ordinal) {
                continue
            }
            if (blockedUnitsSet.contains(unit.id())) {
                continue
            }
            val state = ratingStates[unit.id()] ?: defaultState
            var firstMissingMode: Mode? = null
            var hasIntroducedMode = false
            for (mode in modes) {
                if (state.isIntroduced(mode)) {
                    hasIntroducedMode = true
                }
                if (state.canBeIntroduced(mode, currentTime)) {
                    firstMissingMode = mode
                    if (chosenUnitId == null) {
                        chosenMode = mode
                        chosenUnitId = unit.id()
                    }
                }
            }
            if (hasIntroducedMode && firstMissingMode != null) {
                return Pair(firstMissingMode, unit.id())
            }
        }

        if (chosenMode != null && chosenUnitId != null) {
            return Pair(chosenMode, chosenUnitId)
        }

        if (maxMode != null && maxUnitId != null) {
            return Pair(maxMode, maxUnitId)
        }

        return Pair(modes.random(), unitsWithCards.random().id())
    }

    fun scoreCard(card: Card, mode: Mode, currentTime: Double): Double {
        val defaultState = RatingState()
        var score = 0.0
        val usages = cardIdUses[card.id] ?: emptyList()
        for (usage in usages) {
            if (usage.is_reported) {
                score -= REPORT_PENALTY
            }
            val days = (currentTime - usage.time) / 60.0 / 60.0 / 24.0
            if (days >= 0.0) {
                score -= CARD_USAGE_FACTOR * exp(-CARD_USAGE_DECAY * days)
            }
        }

        for (unitId in card.unitIds()) {
            if (blockedUnitsSet.contains(unitId)) {
                score -= BLOCKED_UNIT_PENALTY
                continue
            }
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
                score -= DIFFICULTY_PENALTY
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

    fun stats(currentTime: Double = System.currentTimeMillis() / 1000.0): DeckStats {
        var waiting = 0
        for (unit in unitsWithCards) {
            if (unit.difficulty().ordinal > difficulty.ordinal) {
                break
            }
            val state = ratingStates[unit.id()] ?: continue
            if (state.isWaiting(modes, currentTime)) {
                waiting++
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
                "modes" to modes.map { it.value },
                "blocked_units" to blockedUnits
            )
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
            val root = JsonParser.parseString(jsonString).asJsonObject

            ratingStates.clear()
            val ratingsElem = root.get("ratings")
            if (ratingsElem != null && ratingsElem.isJsonObject) {
                val ratingsObj = ratingsElem.asJsonObject
                for ((unitIdKey, elem) in ratingsObj.entrySet()) {
                    val ratingsList = mutableListOf<Rating>()
                    if (elem.isJsonArray) {
                        for (item in elem.asJsonArray) {
                            try {
                                val r = gson.fromJson(item, Rating::class.java)
                                if (r != null) ratingsList.add(r)
                            } catch (_: Exception) {}
                        }
                    }
                    ratingStates[unitIdKey] = RatingState(ratingsList)
                }
            }

            cardIdUses.clear()
            val usagesElem = root.get("card_id_uses")
            if (usagesElem != null && usagesElem.isJsonObject) {
                val usagesObj = usagesElem.asJsonObject
                for ((cardIdKey, elem) in usagesObj.entrySet()) {
                    val usagesList = mutableListOf<CardUsage>()
                    if (elem.isJsonArray) {
                        for (item in elem.asJsonArray) {
                            try {
                                val u = gson.fromJson(item, CardUsage::class.java)
                                if (u != null) usagesList.add(u)
                            } catch (_: Exception) {}
                        }
                    }
                    cardIdUses[cardIdKey] = usagesList
                }
            }

            val diffElem = root.get("difficulty")
            if (diffElem != null && !diffElem.isJsonNull) {
                difficulty = Difficulty.fromValue(diffElem.asString)
            }

            val modesElem = root.get("modes")
            if (modesElem != null && modesElem.isJsonArray) {
                val modesList = mutableListOf<Mode>()
                for (elem in modesElem.asJsonArray) {
                    modesList.add(Mode.fromValue(elem.asString))
                }
                modes = modesList
            }

            blockedUnits.clear()
            blockedUnitsSet.clear()
            val blockedElem = root.get("blocked_units")
            if (blockedElem != null && blockedElem.isJsonArray) {
                for (elem in blockedElem.asJsonArray) {
                    val unitId = elem.asString
                    blockedUnits.add(unitId)
                    blockedUnitsSet.add(unitId)
                }
            }

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
