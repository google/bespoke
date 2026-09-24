package com.google.bespoke.data

import android.database.sqlite.SQLiteDatabase
import android.util.LruCache
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.gson.Gson
import com.google.gson.JsonParser
import java.io.Closeable
import java.io.File

class DatasetReader(private val dbFile: File) : Closeable {
    private val db: SQLiteDatabase = try {
        SQLiteDatabase.openDatabase(
            dbFile.absolutePath,
            null,
            SQLiteDatabase.OPEN_READWRITE
        )
    } catch (_: Exception) {
        SQLiteDatabase.openDatabase(
            dbFile.absolutePath,
            null,
            SQLiteDatabase.OPEN_READONLY
        )
    }
    private val gson = Gson()
    private val cardCache = LruCache<String, Card>(256)
    private val unitCache = LruCache<String, UnitItem>(1024)
    private val translationCache = LruCache<String, String>(1024)

    fun getMetadata(): Map<String, String> {
        val meta = mutableMapOf<String, String>()
        try {
            val cursor = db.rawQuery("SELECT key, value FROM metadata", null)
            cursor.use {
                while (it.moveToNext()) {
                    val key = it.getString(0)
                    val value = it.getString(1)
                    meta[key] = value
                }
            }
        } catch (_: Exception) {}
        return meta
    }

    fun getCardCount(): Int {
        if (!db.isOpen) return 0
        try {
            val cursor = db.rawQuery("SELECT count(*) FROM cards", null)
            cursor.use {
                if (it.moveToFirst()) return it.getInt(0)
            }
        } catch (_: Exception) {}
        return 0
    }

    fun getVocabCount(): Int {
        if (!db.isOpen) return 0
        try {
            val cursor = db.rawQuery("SELECT count(*) FROM vocabulary", null)
            cursor.use {
                if (it.moveToFirst()) return it.getInt(0)
            }
        } catch (_: Exception) {}
        return 0
    }

    fun getCard(cardId: String): Card? {
        val cached = cardCache.get(cardId)
        if (cached != null) return cached

        val cursor = db.rawQuery("SELECT json FROM cards WHERE id = ?", arrayOf(cardId))
        cursor.use {
            if (it.moveToFirst()) {
                val jsonStr = it.getString(0)
                val card = parseCardJson(jsonStr)
                if (card != null) {
                    cardCache.put(cardId, card)
                }
                return card
            }
        }
        return null
    }

    fun getAllCards(): List<Card> {
        val cards = mutableListOf<Card>()
        val cursor = db.rawQuery("SELECT json FROM cards", null)
        cursor.use {
            while (it.moveToNext()) {
                val jsonStr = it.getString(0)
                parseCardJson(jsonStr)?.let { card -> cards.add(card) }
            }
        }
        return cards
    }

    fun getCardsForUnit(unitId: String, limit: Int = 1000): List<Card> {
        val cards = mutableListOf<Card>()
        if (!db.isOpen) return cards
        try {
            val query = """
                SELECT c.json FROM cards c
                INNER JOIN card_index idx ON c.id = idx.card_id
                WHERE idx.unit_id = ?
                LIMIT ?
            """.trimIndent()
            val cursor = db.rawQuery(query, arrayOf(unitId, limit.toString()))
            cursor.use {
                while (it.moveToNext()) {
                    val jsonStr = it.getString(0)
                    parseCardJson(jsonStr)?.let { card ->
                        cardCache.put(card.id, card)
                        cards.add(card)
                    }
                }
            }
        } catch (_: Exception) {}
        return cards
    }

    fun getUnitsWithCards(): Set<String> {
        val units = mutableSetOf<String>()
        if (!db.isOpen) return units
        try {
            val cursor = db.rawQuery("SELECT DISTINCT unit_id FROM card_index", null)
            cursor.use {
                while (it.moveToNext()) {
                    units.add(it.getString(0))
                }
            }
        } catch (_: Exception) {}
        return units
    }

    fun getActiveUnits(): List<UnitItem> {
        val list = mutableListOf<UnitItem>()
        if (!db.isOpen) return list
        try {
            val query = """
                SELECT v.id, v.name, v.definition, v.difficulty
                FROM vocabulary v
                WHERE v.id IN (SELECT DISTINCT unit_id FROM card_index)
                ORDER BY CASE v.difficulty
                    WHEN 'A1' THEN 1
                    WHEN 'A2' THEN 2
                    WHEN 'B1' THEN 3
                    WHEN 'B2' THEN 4
                    WHEN 'C1' THEN 5
                    WHEN 'C2' THEN 6
                    ELSE 7
                END ASC, v.rowid ASC
            """.trimIndent()
            val cursor = db.rawQuery(query, null)
            cursor.use {
                while (it.moveToNext()) {
                    val name = it.getString(1)
                    val def = if (it.isNull(2)) "" else it.getString(2)
                    val diff = Difficulty.fromValue(it.getString(3))
                    val item = if (def.isNotEmpty()) DictionaryUnit(name, def, diff) else WordUnit(name, diff)
                    list.add(item)
                    unitCache.put(item.id(), item)
                }
            }
        } catch (_: Exception) {}
        if (list.isEmpty()) {
            val vocab = getVocabulary()
            val activeIds = getUnitsWithCards()
            return vocab.filter { activeIds.contains(it.id()) }
        }
        return list
    }

    fun getActiveTranslations(): Map<String, String> {
        val map = mutableMapOf<String, String>()
        if (!db.isOpen) return map
        try {
            val query = """
                SELECT t.unit_id, t.translation FROM translations t
                WHERE t.unit_id IN (SELECT DISTINCT unit_id FROM card_index)
            """.trimIndent()
            val cursor = db.rawQuery(query, null)
            cursor.use {
                while (it.moveToNext()) {
                    val uid = it.getString(0)
                    val trans = it.getString(1)
                    map[uid] = trans
                    translationCache.put(uid, trans)
                }
            }
        } catch (_: Exception) {}
        return map
    }

    fun getUnit(unitId: String): UnitItem? {
        val cached = unitCache.get(unitId)
        if (cached != null) return cached
        if (!db.isOpen) return null
        try {
            val cursor = db.rawQuery("SELECT name, definition, difficulty FROM vocabulary WHERE id = ?", arrayOf(unitId))
            cursor.use {
                if (it.moveToFirst()) {
                    val name = it.getString(0)
                    val def = if (it.isNull(1)) "" else it.getString(1)
                    val diff = Difficulty.fromValue(it.getString(2))
                    val item = if (def.isNotEmpty()) DictionaryUnit(name, def, diff) else WordUnit(name, diff)
                    unitCache.put(unitId, item)
                    return item
                }
            }
        } catch (_: Exception) {}
        return null
    }

    fun getTranslation(unitId: String): String? {
        val cached = translationCache.get(unitId)
        if (cached != null) return cached
        if (!db.isOpen) return null
        try {
            val cursor = db.rawQuery("SELECT translation FROM translations WHERE unit_id = ?", arrayOf(unitId))
            cursor.use {
                if (it.moveToFirst()) {
                    val trans = it.getString(0)
                    translationCache.put(unitId, trans)
                    return trans
                }
            }
        } catch (_: Exception) {}
        return null
    }

    fun getAudioBlob(filename: String): ByteArray? {
        if (filename.isEmpty() || !db.isOpen) return null

        try {
            // Try exact filename match first
            var cursor = db.rawQuery("SELECT data FROM audio WHERE filename = ?", arrayOf(filename))
            cursor.use {
                if (it.moveToFirst()) {
                    return it.getBlob(0)
                }
            }

            // Try basename fallback (exact indexed match)
            val basename = File(filename).name
            if (basename != filename) {
                cursor = db.rawQuery("SELECT data FROM audio WHERE filename = ?", arrayOf(basename))
                cursor.use {
                    if (it.moveToFirst()) {
                        return it.getBlob(0)
                    }
                }
            }
        } catch (_: Exception) {}

        return null
    }

    fun getTranslations(): Map<String, String> {
        val translations = mutableMapOf<String, String>()
        if (!db.isOpen) return translations
        try {
            val cursor = db.rawQuery("SELECT unit_id, translation FROM translations", null)
            cursor.use {
                while (it.moveToNext()) {
                    val unitId = it.getString(0)
                    val trans = it.getString(1)
                    translations[unitId] = trans
                }
            }
        } catch (_: Exception) {}
        return translations
    }

    fun getVocabulary(): List<UnitItem> {
        val vocabulary = mutableListOf<UnitItem>()
        try {
            val cursor = db.rawQuery("SELECT id, name, definition, difficulty FROM vocabulary", null)
            cursor.use {
                while (it.moveToNext()) {
                    val name = it.getString(1)
                    val definition = if (it.isNull(2)) "" else it.getString(2)
                    val diffStr = it.getString(3)
                    val difficulty = Difficulty.fromValue(diffStr)

                    if (definition.isNotEmpty()) {
                        vocabulary.add(DictionaryUnit(name, definition, difficulty))
                    } else {
                        vocabulary.add(WordUnit(name, difficulty))
                    }
                }
            }
        } catch (_: Exception) {}
        return vocabulary
    }

    fun getCardIndex(): Map<String, List<String>> {
        val index = mutableMapOf<String, MutableList<String>>()
        try {
            val cursor = db.rawQuery("SELECT unit_id, card_id FROM card_index", null)
            cursor.use {
                while (it.moveToNext()) {
                    val unitId = it.getString(0)
                    val cardId = it.getString(1)
                    val list = index.getOrPut(unitId) { mutableListOf() }
                    list.add(cardId)
                }
            }
        } catch (_: Exception) {}
        return index
    }

    fun createDeckEngine(): DeckEngine {
        val meta = getMetadata()
        val targetLang = meta["target_language"] ?: meta["target"] ?: "target"
        val nativeLang = meta["native_language"] ?: meta["native"] ?: "native"
        val unitsWithCards = getActiveUnits()
        val unitLookup = unitsWithCards.associateBy { it.id() }
        val translations = getActiveTranslations()

        return DeckEngine(
            targetLanguageCode = targetLang,
            nativeLanguageCode = nativeLang,
            unitsWithCards = unitsWithCards,
            cardsByUnitId = emptyMap(),
            translations = translations,
            unitLookup = unitLookup,
            cardProvider = { unitId, limit -> getCardsForUnit(unitId, limit) },
            unitProvider = { unitId -> getUnit(unitId) },
            translationProvider = { unitId -> getTranslation(unitId) }
        )
    }

    private fun parseCardJson(jsonStr: String): Card? {
        return try {
            gson.fromJson(jsonStr, Card::class.java)
        } catch (e: Exception) {
            try {
                val root = JsonParser.parseString(jsonStr).asJsonObject
                val id = root.get("id")?.asString ?: return null
                val sentence = root.get("sentence")?.asString ?: ""
                val nativeSentence = root.get("native_sentence")?.asString ?: ""
                val audioFilename = root.get("audio_filename")?.asString ?: ""
                val slowAudioFilename = root.get("slow_audio_filename")?.asString ?: ""
                val nativeAudioFilename = root.get("native_audio_filename")?.asString ?: ""
                val phonetic = if (root.has("phonetic") && !root.get("phonetic").isJsonNull) root.get("phonetic").asString else null
                val notes = if (root.has("notes") && root.get("notes").isJsonArray) {
                    val list = mutableListOf<String>()
                    for (elem in root.getAsJsonArray("notes")) {
                        list.add(elem.asString)
                    }
                    list
                } else emptyList()

                val unitTagsList = mutableListOf<UnitTag>()
                val unitTagsRaw = root.get("unit_tags")
                if (unitTagsRaw != null && unitTagsRaw.isJsonArray) {
                    for (tagObj in unitTagsRaw.asJsonArray) {
                        if (tagObj.isJsonObject) {
                            val obj = tagObj.asJsonObject
                            val occ = obj.get("occurance")?.asString ?: ""
                            val uid = obj.get("unit_id")?.asString ?: ""
                            unitTagsList.add(UnitTag(occ, uid))
                        }
                    }
                }

                Card(
                    id = id,
                    sentence = sentence,
                    native_sentence = nativeSentence,
                    audio_filename = audioFilename,
                    slow_audio_filename = slowAudioFilename,
                    native_audio_filename = nativeAudioFilename,
                    phonetic = phonetic,
                    unit_tags = unitTagsList,
                    notes = notes
                )
            } catch (_: Exception) {
                null
            }
        }
    }

    override fun close() {
        if (db.isOpen) {
            db.close()
        }
    }
}
