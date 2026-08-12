package com.google.bespoke

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.model.DictionaryUnit
import com.google.bespoke.model.WordUnit
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.FileOutputStream

@RunWith(RobolectricTestRunner::class)
class DatasetReaderTest {

    private lateinit var context: Context
    private lateinit var dbFile: File
    private lateinit var reader: DatasetReader

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        dbFile = File(context.filesDir, "test_deck.db")
        context.assets.open("sample_deck.db").use { input ->
            FileOutputStream(dbFile).use { output ->
                input.copyTo(output)
            }
        }
        reader = DatasetReader(dbFile)
    }

    @Test
    fun testMetadata() {
        val meta = reader.getMetadata()
        assertEquals("japanese", meta["target_language"])
        assertEquals("english", meta["native_language"])
        assertEquals("2", meta["card_count"])
    }

    @Test
    fun testGetCard() {
        val card = reader.getCard("card_001")
        assertNotNull(card)
        assertEquals("card_001", card!!.id)
        assertEquals("大学生は学生より年上です。", card.sentence)
        assertEquals("A university student is older than a student.", card.native_sentence)
        assertEquals("だいがくせいはがくせいよりとしうえです。", card.phonetic)
        assertEquals(2, card.unit_tags.size)
        assertEquals(listOf("大学生", "学生 - student"), card.unitIds())
    }

    @Test
    fun testGetAllCards() {
        val cards = reader.getAllCards()
        assertEquals(2, cards.size)
        val ids = cards.map { it.id }.toSet()
        assertEquals(setOf("card_001", "card_002"), ids)
    }

    @Test
    fun testGetCardsForUnit() {
        val cards = reader.getCardsForUnit("大学生")
        assertEquals(1, cards.size)
        assertEquals("card_001", cards[0].id)

        val workCards = reader.getCardsForUnit("仕事 - work")
        assertEquals(1, workCards.size)
        assertEquals("card_002", workCards[0].id)
    }

    @Test
    fun testGetAudioBlob() {
        val blobExact = reader.getAudioBlob("cards/japanese_english/audio_1.ogg")
        assertNotNull(blobExact)
        assertTrue(blobExact!!.isNotEmpty())
        val blobString = String(blobExact, Charsets.ISO_8859_1)
        assertTrue(blobString.contains("OggS"))

        val blobBasename = reader.getAudioBlob("audio_1.ogg")
        assertNotNull(blobBasename)
        assertArrayEquals(blobExact, blobBasename)

        val missingBlob = reader.getAudioBlob("non_existent_audio.ogg")
        assertNull(missingBlob)
    }

    @Test
    fun testTranslations() {
        val trans = reader.getTranslations()
        assertEquals("university student", trans["大学生"])
        assertEquals("student", trans["学生 - student"])
        assertEquals("I, me", trans["私"])
        assertEquals("work, job", trans["仕事 - work"])
    }

    @Test
    fun testVocabulary() {
        val vocab = reader.getVocabulary()
        assertEquals(4, vocab.size)
        val vocabMap = vocab.associateBy { it.id() }

        assertTrue(vocabMap["大学生"] is WordUnit)
        assertTrue(vocabMap["学生 - student"] is DictionaryUnit)
        assertEquals("student", (vocabMap["学生 - student"] as DictionaryUnit).definition())
    }

    @Test
    fun testCardIndex() {
        val index = reader.getCardIndex()
        assertEquals(listOf("card_001"), index["大学生"])
        assertEquals(listOf("card_001"), index["学生 - student"])
        assertEquals(listOf("card_002"), index["私"])
        assertEquals(listOf("card_002"), index["仕事 - work"])
    }

    @Test
    fun testCreateDeckEngine() {
        val deck = reader.createDeckEngine()
        assertEquals("japanese", deck.targetLanguageCode)
        assertEquals("english", deck.nativeLanguageCode)
        assertEquals(4, deck.unitsWithCards.size)

        val (mode, card) = deck.draw()
        assertNotNull(card)
        assertNotNull(mode)
        assertEquals("card_001", card.id)
    }

    @Test
    fun testProgressFileSanitization() {
        val safeFile = com.google.bespoke.data.DeckRepository.getProgressFile(context, "japanese")
        assertEquals("deck_japanese.json", safeFile.name)
        assertTrue(safeFile.canonicalPath.startsWith(context.filesDir.canonicalPath))

        val traversalAttempt = com.google.bespoke.data.DeckRepository.getProgressFile(context, "../../evil_target")
        assertTrue(traversalAttempt.canonicalPath.startsWith(context.filesDir.canonicalPath))
        assertFalse(traversalAttempt.name.contains(".."))
    }
}
