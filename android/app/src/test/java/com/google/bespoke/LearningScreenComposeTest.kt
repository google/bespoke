package com.google.bespoke

import android.content.Context
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.audio.AudioPlayer
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.ui.BackCardView
import com.google.bespoke.ui.FrontCardView
import com.google.bespoke.ui.LearningScreen
import com.google.bespoke.ui.theme.BespokeTheme
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.FileOutputStream

@RunWith(RobolectricTestRunner::class)
class LearningScreenComposeTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private lateinit var context: Context
    private lateinit var dbFile: File
    private lateinit var reader: DatasetReader
    private lateinit var deck: DeckEngine

    private val fakeAudioPlayer = object : AudioPlayer {
        var lastPlayedBytes: ByteArray? = null
        var lastPlayedFile: String? = null
        var isAudioPlaying = false

        override fun playBytes(audioBytes: ByteArray, onComplete: (() -> Unit)?) {
            lastPlayedBytes = audioBytes
            isAudioPlaying = true
            onComplete?.invoke()
            isAudioPlaying = false
        }

        override fun playFile(filePath: String, onComplete: (() -> Unit)?) {
            lastPlayedFile = filePath
            isAudioPlaying = true
            onComplete?.invoke()
            isAudioPlaying = false
        }

        override fun stop() {
            isAudioPlaying = false
        }

        override fun isPlaying(): Boolean = isAudioPlaying

        override fun release() {
            isAudioPlaying = false
        }
    }

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        dbFile = File(context.filesDir, "test_compose_deck.db")
        val resourceStream = LearningScreenComposeTest::class.java.classLoader?.getResourceAsStream("sample_deck.db")
            ?: throw IllegalStateException("sample_deck.db resource not found in test resources")
        resourceStream.use { input ->
            FileOutputStream(dbFile).use { output ->
                input.copyTo(output)
            }
        }
        reader = DatasetReader(dbFile)
        deck = reader.createDeckEngine()
    }

    @Test
    fun testFrontViewListenMode() {
        val card = reader.getCard("card_001")!!
        val stats = DeckStats(waiting = 5, known = 2, mature = 1)
        var flipped = false

        composeTestRule.setContent {
            BespokeTheme {
                FrontCardView(
                    card = card,
                    mode = Mode.LISTEN,
                    stats = stats,
                    onFlip = { flipped = true },
                    onPlayAudio = {}
                )
            }
        }

        composeTestRule.onNodeWithTag("FrontCardView").assertIsDisplayed()
        composeTestRule.onNodeWithTag("AudioPlayerCard").assertIsDisplayed()
        composeTestRule.onNodeWithText("Play").assertIsDisplayed()
        composeTestRule.onNodeWithText("Slow").assertIsDisplayed()
        composeTestRule.onNodeWithText("To Do: 5").assertIsDisplayed()
        composeTestRule.onNodeWithText("Known: 2").assertIsDisplayed()
        composeTestRule.onNodeWithText("Mature: 1").assertIsDisplayed()

        composeTestRule.onNodeWithTag("FlipButton").performClick()
        assertTrue(flipped)
    }

    @Test
    fun testFrontViewSpeakMode() {
        val card = reader.getCard("card_001")!!
        val stats = DeckStats(0, 0, 0)

        composeTestRule.setContent {
            BespokeTheme {
                FrontCardView(
                    card = card,
                    mode = Mode.SPEAK,
                    stats = stats,
                    onFlip = {},
                    onPlayAudio = {}
                )
            }
        }

        composeTestRule.onNodeWithText("Speak the sentence!").assertIsDisplayed()
        composeTestRule.onNodeWithText(card.native_sentence).assertIsDisplayed()
    }

    @Test
    fun testFrontViewReadMode() {
        val card = reader.getCard("card_001")!!
        val stats = DeckStats(0, 0, 0)

        composeTestRule.setContent {
            BespokeTheme {
                FrontCardView(
                    card = card,
                    mode = Mode.READ,
                    stats = stats,
                    onFlip = {},
                    onPlayAudio = {}
                )
            }
        }
        composeTestRule.onNodeWithText(card.sentence).assertIsDisplayed()
    }

    @Test
    fun testFrontViewWriteMode() {
        val card = reader.getCard("card_001")!!
        val stats = DeckStats(0, 0, 0)

        composeTestRule.setContent {
            BespokeTheme {
                FrontCardView(
                    card = card,
                    mode = Mode.WRITE,
                    stats = stats,
                    onFlip = {},
                    onPlayAudio = {}
                )
            }
        }
        composeTestRule.onNodeWithText("Write the sentence!").assertIsDisplayed()
        composeTestRule.onNodeWithText(card.native_sentence).assertIsDisplayed()
    }

    @Test
    fun testBackCardViewInteractionsAndColorCycling() {
        val card = reader.getCard("card_001")!!
        val ratings = mutableMapOf<String, Int>("大学生" to 0, "学生 - student" to 0)
        var nextReported: Boolean? = null

        composeTestRule.setContent {
            val stateRatings = remember { mutableStateMapOf<String, Int>("大学生" to 0, "学生 - student" to 0) }
            BespokeTheme {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    BackCardView(
                        card = card,
                        mode = Mode.LISTEN,
                        unitLookup = deck.unitLookup,
                        translations = deck.translations,
                        ratings = stateRatings,
                        onRateWord = { uid, score ->
                            stateRatings[uid] = score
                            ratings[uid] = score
                        },
                        onAllSuccess = {
                            stateRatings["大学生"] = 3
                            stateRatings["学生 - student"] = 3
                            ratings["大学生"] = 3
                            ratings["学生 - student"] = 3
                        },
                        onNext = { isReported ->
                            nextReported = isReported
                        },
                        onPlayAudio = {}
                    )
                }
            }
        }

        // Verify elements on Back view
        composeTestRule.onNodeWithTag("BackCardView").assertIsDisplayed()
        composeTestRule.onNodeWithText("Play").assertIsDisplayed()
        composeTestRule.onNodeWithText("Slow").assertIsDisplayed()
        composeTestRule.onNodeWithText("Native").assertIsDisplayed()
        composeTestRule.onNodeWithText(card.sentence).assertIsDisplayed()
        composeTestRule.onNodeWithText(card.phonetic!!).assertIsDisplayed()
        composeTestRule.onNodeWithText(card.native_sentence).assertIsDisplayed()
        composeTestRule.onNodeWithTag("RateWordsHeader").assertIsDisplayed()

        // Click word button "大学生" to cycle rating 0 -> 3
        composeTestRule.onNodeWithTag("WordButton_大学生").performScrollTo().performClick()
        assertEquals(3, ratings["大学生"])
        composeTestRule.onNodeWithTag("DefinitionLabel").assertTextEquals("university student")

        // Click again: 3 -> 1
        composeTestRule.onNodeWithTag("WordButton_大学生").performScrollTo().performClick()
        assertEquals(1, ratings["大学生"])

        // Click again: 1 -> 0
        composeTestRule.onNodeWithTag("WordButton_大学生").performScrollTo().performClick()
        assertEquals(0, ratings["大学生"])

        // Test All Success button
        composeTestRule.onNodeWithTag("AllSuccessButton").performScrollTo().performClick()
        assertEquals(3, ratings["大学生"])
        assertEquals(3, ratings["学生 - student"])

        // Toggle Report Error switch
        composeTestRule.onNodeWithTag("ReportErrorSwitch").performScrollTo().performClick()

        // Click Next button
        composeTestRule.onNodeWithTag("NextButton").performScrollTo().performClick()
        assertNotNull(nextReported)
        assertTrue(nextReported!!)
    }

    @Test
    fun testFullLearningScreenFlow() {
        var progressSaved = false

        composeTestRule.setContent {
            BespokeTheme {
                LearningScreen(
                    deckEngine = deck,
                    datasetReader = reader,
                    audioPlayer = fakeAudioPlayer,
                    onSaveProgress = { progressSaved = true }
                )
            }
        }

        // 1. Verify Initial Front Card
        composeTestRule.onNodeWithTag("FrontCardView").assertIsDisplayed()

        // 2. Flip to back
        composeTestRule.onNodeWithTag("FlipButton").performScrollTo().performClick()
        composeTestRule.onNodeWithTag("BackCardView").assertIsDisplayed()

        // 3. Mark all success
        composeTestRule.onNodeWithTag("AllSuccessButton").performScrollTo().performClick()

        // 4. Click Next
        composeTestRule.onNodeWithTag("NextButton").performScrollTo().performClick()

        // 5. Verifies next card is loaded on front view and progress was saved
        composeTestRule.onNodeWithTag("FrontCardView").assertIsDisplayed()
        assertTrue(progressSaved)
    }
}
