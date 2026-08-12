package com.google.bespoke

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.srs.RatingState
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class E2EPipelineStressTest {

    private lateinit var context: Context
    private lateinit var testDir: File

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        testDir = File(context.filesDir, "e2e_stress_test").apply {
            mkdirs()
        }
    }

    private fun createCustomDatabase(
        dbFile: File,
        cards: List<Card>,
        audioMap: Map<String, ByteArray>,
        translations: Map<String, String>,
        vocabulary: List<Pair<String, Pair<String, String>>>, // name, (def, diff)
        indexMap: Map<String, List<String>>,
        metadata: Map<String, String>
    ) {
        if (dbFile.exists()) dbFile.delete()
        val db = SQLiteDatabase.openOrCreateDatabase(dbFile, null)
        val gson = Gson()

        db.execSQL("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execSQL("CREATE TABLE cards (id TEXT PRIMARY KEY, sentence TEXT NOT NULL, native_sentence TEXT NOT NULL, phonetic TEXT, audio_filename TEXT NOT NULL, slow_audio_filename TEXT NOT NULL, native_audio_filename TEXT NOT NULL, unit_tags_json TEXT NOT NULL, notes_json TEXT NOT NULL, json TEXT NOT NULL)")
        db.execSQL("CREATE TABLE audio (filename TEXT PRIMARY KEY, data BLOB NOT NULL)")
        db.execSQL("CREATE TABLE translations (unit_id TEXT PRIMARY KEY, translation TEXT NOT NULL)")
        db.execSQL("CREATE TABLE vocabulary (id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT, difficulty TEXT NOT NULL)")
        db.execSQL("CREATE TABLE card_index (unit_id TEXT NOT NULL, card_id TEXT NOT NULL, PRIMARY KEY (unit_id, card_id))")

        // Metadata
        val metaStmt = db.compileStatement("INSERT INTO metadata (key, value) VALUES (?, ?)")
        for ((k, v) in metadata) {
            metaStmt.bindString(1, k)
            metaStmt.bindString(2, v)
            metaStmt.executeInsert()
        }

        // Cards
        val cardStmt = db.compileStatement("INSERT INTO cards (id, sentence, native_sentence, phonetic, audio_filename, slow_audio_filename, native_audio_filename, unit_tags_json, notes_json, json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
        for (card in cards) {
            cardStmt.bindString(1, card.id)
            cardStmt.bindString(2, card.sentence)
            cardStmt.bindString(3, card.native_sentence)
            if (card.phonetic != null) cardStmt.bindString(4, card.phonetic) else cardStmt.bindNull(4)
            cardStmt.bindString(5, card.audio_filename)
            cardStmt.bindString(6, card.slow_audio_filename)
            cardStmt.bindString(7, card.native_audio_filename)
            cardStmt.bindString(8, gson.toJson(card.unit_tags))
            cardStmt.bindString(9, gson.toJson(card.notes))
            cardStmt.bindString(10, gson.toJson(card))
            cardStmt.executeInsert()
        }

        // Audio
        val audioStmt = db.compileStatement("INSERT INTO audio (filename, data) VALUES (?, ?)")
        for ((fn, data) in audioMap) {
            audioStmt.bindString(1, fn)
            audioStmt.bindBlob(2, data)
            audioStmt.executeInsert()
        }

        // Translations
        val transStmt = db.compileStatement("INSERT INTO translations (unit_id, translation) VALUES (?, ?)")
        for ((uid, trans) in translations) {
            transStmt.bindString(1, uid)
            transStmt.bindString(2, trans)
            transStmt.executeInsert()
        }

        // Vocabulary
        val vocabStmt = db.compileStatement("INSERT INTO vocabulary (id, name, definition, difficulty) VALUES (?, ?, ?, ?)")
        for ((name, pair) in vocabulary) {
            val (def, diff) = pair
            val uid = if (def.isNotEmpty()) "$name - $def" else name
            vocabStmt.bindString(1, uid)
            vocabStmt.bindString(2, name)
            if (def.isNotEmpty()) vocabStmt.bindString(3, def) else vocabStmt.bindNull(3)
            vocabStmt.bindString(4, diff)
            vocabStmt.executeInsert()
        }

        // Card Index
        val indexStmt = db.compileStatement("INSERT INTO card_index (unit_id, card_id) VALUES (?, ?)")
        for ((uid, cardIds) in indexMap) {
            for (cid in cardIds) {
                indexStmt.bindString(1, uid)
                indexStmt.bindString(2, cid)
                indexStmt.executeInsert()
            }
        }

        db.close()
    }

    @Test
    fun testFullDataPipelineRoundtripAndCardProgression() {
        val dbFile = File(testDir, "multilingual_roundtrip.db")
        val audioData1 = byteArrayOf(0x4f, 0x67, 0x67, 0x53, 0x00, 0x02, 0x01, 0x02, 0x03, 0x04)
        val audioData2 = byteArrayOf(0x4f, 0x67, 0x67, 0x53, 0x00, 0x02, 0x05, 0x06, 0x07, 0x08)

        val card1 = Card(
            id = "c_jp_1",
            sentence = "猫🐱が好きです。",
            native_sentence = "I like cats 🐱.",
            phonetic = "ねこがすきです。",
            audio_filename = "cards/japanese_english/audio_1.ogg",
            slow_audio_filename = "cards/japanese_english/slow_1.ogg",
            native_audio_filename = "cards/japanese_english/native_1.ogg",
            unit_tags = listOf(UnitTag("猫🐱", "猫 - cat")),
            notes = listOf("Animal vocab", "Emoji: 🐱")
        )

        val card2 = Card(
            id = "c_de_2",
            sentence = "Hunde 🐶 bellen laut im Garten.",
            native_sentence = "Dogs 🐶 bark loudly in the garden.",
            phonetic = null,
            audio_filename = "audio_2.ogg",
            slow_audio_filename = "slow_2.ogg",
            native_audio_filename = "native_2.ogg",
            unit_tags = listOf(UnitTag("Hunde 🐶", "Hund - dog")),
            notes = listOf("German plural noun")
        )

        val card3 = Card(
            id = "c_ar_3",
            sentence = "مرحبا بالعالم! 🌍",
            native_sentence = "Hello world! 🌍",
            phonetic = "Marhaban",
            audio_filename = "audio_3.ogg",
            slow_audio_filename = "slow_3.ogg",
            native_audio_filename = "native_3.ogg",
            unit_tags = listOf(UnitTag("مرحبا", "مرحبا - hello")),
            notes = listOf("Arabic greeting")
        )

        val cards = listOf(card1, card2, card3)
        val audioMap = mapOf(
            "cards/japanese_english/audio_1.ogg" to audioData1,
            "cards/japanese_english/slow_1.ogg" to audioData1,
            "cards/japanese_english/native_1.ogg" to audioData1,
            "audio_2.ogg" to audioData2,
            "slow_2.ogg" to audioData2,
            "native_2.ogg" to audioData2,
            "audio_3.ogg" to audioData1,
            "slow_3.ogg" to audioData1,
            "native_3.ogg" to audioData1
        )
        val translations = mapOf(
            "猫 - cat" to "cat, feline 🐱",
            "Hund - dog" to "dog, hound 🐶",
            "مرحبا - hello" to "hello, greeting"
        )
        val vocabulary = listOf(
            "猫" to Pair("cat", "A1"),
            "Hund" to Pair("dog", "A1"),
            "مرحبا" to Pair("hello", "A2")
        )
        val indexMap = mapOf(
            "猫 - cat" to listOf("c_jp_1"),
            "Hund - dog" to listOf("c_de_2"),
            "مرحبا - hello" to listOf("c_ar_3")
        )
        val metadata = mapOf(
            "target_language" to "japanese",
            "native_language" to "english",
            "card_count" to "3",
            "version" to "1.0"
        )

        createCustomDatabase(dbFile, cards, audioMap, translations, vocabulary, indexMap, metadata)

        // 1. Open with DatasetReader
        DatasetReader(dbFile).use { reader ->
            val meta = reader.getMetadata()
            assertEquals("japanese", meta["target_language"])
            assertEquals("english", meta["native_language"])
            assertEquals("3", meta["card_count"])

            // Cards extraction
            val allCards = reader.getAllCards()
            assertEquals(3, allCards.size)
            val c1 = reader.getCard("c_jp_1")
            assertNotNull(c1)
            assertEquals("猫🐱が好きです。", c1!!.sentence)
            assertEquals("ねこがすきです。", c1.phonetic)

            val c2 = reader.getCard("c_de_2")
            assertNotNull(c2)
            assertNull(c2!!.phonetic)

            // Audio extraction (exact and basename)
            val blob1 = reader.getAudioBlob("cards/japanese_english/audio_1.ogg")
            assertNotNull(blob1)
            assertArrayEquals(audioData1, blob1)

            val blob1Basename = reader.getAudioBlob("audio_1.ogg")
            assertNotNull(blob1Basename)
            assertArrayEquals(audioData1, blob1Basename)

            // Translations
            val trans = reader.getTranslations()
            assertEquals("cat, feline 🐱", trans["猫 - cat"])
            assertEquals("hello, greeting", trans["مرحبا - hello"])

            // Vocabulary
            val vocab = reader.getVocabulary()
            assertEquals(3, vocab.size)
            val vMap = vocab.associateBy { it.id() }
            assertTrue(vMap["猫 - cat"] is DictionaryUnit)
            assertEquals("cat", (vMap["猫 - cat"] as DictionaryUnit).definition())
            assertEquals(Difficulty.A1, vMap["猫 - cat"]!!.difficulty())
            assertEquals(Difficulty.A2, vMap["مرحبا - hello"]!!.difficulty())

            // Card index
            val idx = reader.getCardIndex()
            assertEquals(listOf("c_jp_1"), idx["猫 - cat"])
            assertEquals(listOf("c_de_2"), idx["Hund - dog"])

            // 2. Create DeckEngine and run simulated learning session
            val deck = reader.createDeckEngine()
            deck.setModes(listOf(Mode.LISTEN, Mode.SPEAK))

            // Initial draw at t=1000.0: should draw c_jp_1 on LISTEN
            val t0 = 1000.0
            val (m1, cardDraw1) = deck.draw(currentTime = t0)
            assertEquals(Mode.LISTEN, m1)
            assertEquals("c_jp_1", cardDraw1.id)

            // Rate Green (3)
            val unit1 = vocab.first { it.id() == "猫 - cat" }
            deck.rate(unit1, m1, 3, currentTime = t0)
            deck.logUsage(cardDraw1.id, isReported = false, currentTime = t0)

            // Next draw at t=1001.0: unit1 is blocked (20h), so draw c_de_2 on LISTEN
            val (m2, cardDraw2) = deck.draw(currentTime = t0 + 1.0)
            assertEquals(Mode.LISTEN, m2)
            assertEquals("c_de_2", cardDraw2.id)

            // Rate Red (1) on c_de_2
            val unit2 = vocab.first { it.id() == "Hund - dog" }
            deck.rate(unit2, m2, 1, currentTime = t0 + 1.0)
            deck.logUsage(cardDraw2.id, isReported = false, currentTime = t0 + 1.0)

            // Next draw at t=1002.0: c_jp_1 and c_de_2 are blocked, draw c_ar_3
            val (m3, cardDraw3) = deck.draw(currentTime = t0 + 2.0)
            assertEquals(Mode.LISTEN, m3)
            assertEquals("c_ar_3", cardDraw3.id)

            // Advance time past Red block of unit2 (10 min + 10s = 610s): unit2 unblocks with high urgency
            val tUnblockRed = t0 + 1.0 + 610.0
            val (m4, cardDraw4) = deck.draw(currentTime = tUnblockRed)
            assertEquals(Mode.LISTEN, m4)
            assertEquals("c_de_2", cardDraw4.id)

            // Check stats
            val stats = deck.stats(currentTime = tUnblockRed)
            assertTrue(stats.waiting >= 0)

            // 3. Save state to JSON
            val stateFile = File(testDir, "saved_deck_state.json")
            deck.save(stateFile)
            assertTrue(stateFile.exists())
            val savedJson = stateFile.readText()
            assertTrue(savedJson.contains("japanese"))
            assertTrue(savedJson.contains("猫 - cat"))
            assertTrue(savedJson.contains("Hund - dog"))

            // 4. Restore state into a fresh DeckEngine
            val restoredDeck = reader.createDeckEngine()
            restoredDeck.load(stateFile)

            // Check identical ratings and usages
            assertEquals(deck.getRatingStates().size, restoredDeck.getRatingStates().size)
            assertEquals(deck.getCardUsages().size, restoredDeck.getCardUsages().size)

            // Draw after restoration gives identical deterministic result
            val (mRestored, cardRestored) = restoredDeck.draw(currentTime = tUnblockRed)
            assertEquals(m4, mRestored)
            assertEquals(cardDraw4.id, cardRestored.id)
        }
    }

    @Test
    fun testLegacyOldCardJsonInSQLiteDatabase() {
        val dbFile = File(testDir, "legacy_cards.db")
        if (dbFile.exists()) dbFile.delete()
        val db = SQLiteDatabase.openOrCreateDatabase(dbFile, null)

        db.execSQL("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execSQL("CREATE TABLE cards (id TEXT PRIMARY KEY, sentence TEXT NOT NULL, native_sentence TEXT NOT NULL, phonetic TEXT, audio_filename TEXT NOT NULL, slow_audio_filename TEXT NOT NULL, native_audio_filename TEXT NOT NULL, unit_tags_json TEXT NOT NULL, notes_json TEXT NOT NULL, json TEXT NOT NULL)")
        db.execSQL("CREATE TABLE audio (filename TEXT PRIMARY KEY, data BLOB NOT NULL)")
        db.execSQL("CREATE TABLE translations (unit_id TEXT PRIMARY KEY, translation TEXT NOT NULL)")
        db.execSQL("CREATE TABLE vocabulary (id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT, difficulty TEXT NOT NULL)")
        db.execSQL("CREATE TABLE card_index (unit_id TEXT NOT NULL, card_id TEXT NOT NULL, PRIMARY KEY (unit_id, card_id))")

        // Metadata
        db.execSQL("INSERT INTO metadata (key, value) VALUES ('target_language', 'japanese'), ('native_language', 'english')")

        // Insert OldCard JSON format (with units array and unit_tags map)
        val oldCardJson = """
            {
                "id": "old_c1",
                "sentence": "これは本です。",
                "native_sentence": "This is a book.",
                "audio_filename": "audio.ogg",
                "slow_audio_filename": "slow.ogg",
                "native_audio_filename": "native.ogg",
                "phonetic": "これわほんです。",
                "units": ["これ", "本"],
                "unit_tags": {
                    "これ": "これ",
                    "本": "本 - book"
                },
                "notes": ["Old card note"]
            }
        """.trimIndent()

        val stmt = db.compileStatement("INSERT INTO cards (id, sentence, native_sentence, phonetic, audio_filename, slow_audio_filename, native_audio_filename, unit_tags_json, notes_json, json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
        stmt.bindString(1, "old_c1")
        stmt.bindString(2, "これは本です。")
        stmt.bindString(3, "This is a book.")
        stmt.bindString(4, "これわほんです。")
        stmt.bindString(5, "audio.ogg")
        stmt.bindString(6, "slow.ogg")
        stmt.bindString(7, "native.ogg")
        stmt.bindString(8, "[]")
        stmt.bindString(9, "[\"Old card note\"]")
        stmt.bindString(10, oldCardJson)
        stmt.executeInsert()

        db.execSQL("INSERT INTO audio (filename, data) VALUES ('audio.ogg', X'4F6767530002')")
        db.execSQL("INSERT INTO audio (filename, data) VALUES ('slow.ogg', X'4F6767530002')")
        db.execSQL("INSERT INTO audio (filename, data) VALUES ('native.ogg', X'4F6767530002')")
        db.execSQL("INSERT INTO vocabulary (id, name, definition, difficulty) VALUES ('これ', 'これ', NULL, 'A1'), ('本 - book', '本', 'book', 'A1')")
        db.execSQL("INSERT INTO card_index (unit_id, card_id) VALUES ('これ', 'old_c1'), ('本 - book', 'old_c1')")

        db.close()

        DatasetReader(dbFile).use { reader ->
            val card = reader.getCard("old_c1")
            assertNotNull(card)
            assertEquals("old_c1", card!!.id)
            assertEquals("これは本です。", card.sentence)
            assertEquals(2, card.unit_tags.size)
            assertEquals("これ", card.unit_tags[0].occurance)
            assertEquals("これ", card.unit_tags[0].unit_id)
            assertEquals("本", card.unit_tags[1].occurance)
            assertEquals("本 - book", card.unit_tags[1].unit_id)

            val deck = reader.createDeckEngine()
            val (mode, drawnCard) = deck.draw()
            assertEquals("old_c1", drawnCard.id)
            assertNotNull(mode)
        }
    }
}
