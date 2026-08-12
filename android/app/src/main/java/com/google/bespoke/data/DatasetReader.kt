package com.google.bespoke.data

import android.database.sqlite.SQLiteDatabase
import android.util.LruCache
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
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
        return cards
    }

    fun getUnitsWithCards(): Set<String> {
        val units = mutableSetOf<String>()
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

    fun getAudioBlob(filename: String): ByteArray? {
        if (filename.isEmpty()) return null

        try {
            // Try exact filename match first
            var cursor = db.rawQuery("SELECT data FROM audio WHERE filename = ?", arrayOf(filename))
            cursor.use {
                if (it.moveToFirst()) {
                    return it.getBlob(0)
                }
            }

            // Try basename fallback
            val basename = File(filename).name
            cursor = db.rawQuery(
                "SELECT data FROM audio WHERE filename = ? OR filename LIKE ?",
                arrayOf(basename, "%/$basename")
            )
            cursor.use {
                if (it.moveToFirst()) {
                    return it.getBlob(0)
                }
            }
        } catch (_: Exception) {}

        return null
    }

    fun getTranslations(): Map<String, String> {
        val translations = mutableMapOf<String, String>()
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
        val vocab = getVocabulary()
        val activeUnitIds = getUnitsWithCards()
        val unitsWithCards = vocab.filter { activeUnitIds.contains(it.id()) }
        val unitLookup = vocab.associateBy { it.id() }
        val translations = getTranslations()

        return DeckEngine(
            targetLanguageCode = targetLang,
            nativeLanguageCode = nativeLang,
            unitsWithCards = unitsWithCards,
            cardsByUnitId = emptyMap(),
            translations = translations,
            unitLookup = unitLookup,
            cardProvider = { unitId, limit -> getCardsForUnit(unitId, limit) }
        )
    }

    private fun parseCardJson(jsonStr: String): Card? {
        return try {
            gson.fromJson(jsonStr, Card::class.java)
        } catch (e: Exception) {
            try {
                val mapType = object : TypeToken<Map<String, Any>>() {}.type
                val map: Map<String, Any> = gson.fromJson(jsonStr, mapType)
                val id = map["id"] as? String ?: return null
                val sentence = map["sentence"] as? String ?: ""
                val nativeSentence = map["native_sentence"] as? String ?: ""
                val audioFilename = map["audio_filename"] as? String ?: ""
                val slowAudioFilename = map["slow_audio_filename"] as? String ?: ""
                val nativeAudioFilename = map["native_audio_filename"] as? String ?: ""
                val phonetic = map["phonetic"] as? String
                val notes = (map["notes"] as? List<*>)?.map { it.toString() } ?: emptyList()

                val unitTagsList = mutableListOf<UnitTag>()
                val unitTagsRaw = map["unit_tags"]
                if (unitTagsRaw is List<*>) {
                    for (tagObj in unitTagsRaw) {
                        if (tagObj is Map<*, *>) {
                            val occ = tagObj["occurance"]?.toString() ?: ""
                            val uid = tagObj["unit_id"]?.toString() ?: ""
                            unitTagsList.add(UnitTag(occ, uid))
                        }
                    }
                } else if (unitTagsRaw is Map<*, *>) {
                    for ((k, v) in unitTagsRaw) {
                        unitTagsList.add(UnitTag(k.toString(), v.toString()))
                    }
                    unitTagsList.sortBy { sentence.indexOf(it.occurance) }
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
