package com.google.bespoke

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.audio.AudioPlayer
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.data.DeckRepository
import com.google.bespoke.model.DeckInfo
import com.google.bespoke.model.Difficulty
import com.google.bespoke.model.Mode
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.ui.LearningScreen
import com.google.bespoke.ui.StartScreen
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
class NavigationFlowComposeTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<ComponentActivity>()

    private lateinit var context: Context
    private lateinit var dbFile: File

    private val fakeAudioPlayer = object : AudioPlayer {
        override fun playBytes(audioBytes: ByteArray, onComplete: (() -> Unit)?) { onComplete?.invoke() }
        override fun playFile(filePath: String, onComplete: (() -> Unit)?) { onComplete?.invoke() }
        override fun stop() {}
        override fun isPlaying(): Boolean = false
        override fun release() {}
    }

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        dbFile = File(context.filesDir, "sample_deck.db")
        context.assets.open("sample_deck.db").use { input ->
            FileOutputStream(dbFile).use { output ->
                input.copyTo(output)
            }
        }
    }

    @Test
    fun testCompleteStudySessionFlowWithSpacedRepetition() {
        val reader = DatasetReader(dbFile)
        val deck = reader.createDeckEngine()
        deck.setDifficulty(Difficulty.A1)
        deck.setModes(listOf(Mode.LISTEN, Mode.SPEAK))

        val deckInfo = DeckInfo(
            id = "sample_deck.db",
            title = "English -> Japanese (Sample Deck)",
            targetLanguage = "Japanese",
            nativeLanguage = "English",
            file = dbFile,
            cardCount = 3,
            vocabCount = 6
        )

        var activeSessionInfo by mutableStateOf<DeckInfo?>(null)
        var engine by mutableStateOf<DeckEngine?>(null)
        var datasetReader by mutableStateOf<DatasetReader?>(null)

        composeTestRule.setContent {
            BespokeTheme {
                val currentInfo = activeSessionInfo
                val currentEngine = engine
                val currentReader = datasetReader

                if (currentInfo != null && currentEngine != null && currentReader != null) {
                    LearningScreen(
                        deckEngine = currentEngine,
                        datasetReader = currentReader,
                        audioPlayer = fakeAudioPlayer,
                        onSaveProgress = {
                            DeckRepository.saveProgress(context, currentEngine)
                        },
                        onNavigateBack = {
                            DeckRepository.saveProgress(context, currentEngine)
                            activeSessionInfo = null
                        }
                    )
                } else {
                    StartScreen(
                        availableDecks = listOf(deckInfo),
                        onStartDeck = { info, diff, modes, assume ->
                            val (r, e) = DeckRepository.prepareDeck(context, info, diff, modes, assume)
                            datasetReader = r
                            engine = e
                            activeSessionInfo = info
                        }
                    )
                }
            }
        }

        // 1. Initial view is StartScreen
        composeTestRule.onNodeWithTag("StartScreen").assertIsDisplayed()

        // 2. Click Start Learning
        composeTestRule.onNodeWithTag("StartLearningButton").performScrollTo().performClick()

        // 3. View is now LearningScreen
        composeTestRule.onNodeWithTag("LearningScreen").assertIsDisplayed()
        composeTestRule.onNodeWithTag("FrontCardView").assertIsDisplayed()

        // 4. Flip and rate card
        composeTestRule.onNodeWithTag("FlipButton").performScrollTo().performClick()
        composeTestRule.onNodeWithTag("AllSuccessButton").performScrollTo().performClick()
        composeTestRule.onNodeWithTag("NextButton").performScrollTo().performClick()

        // 5. Trigger hardware back button via BackHandler
        composeTestRule.activityRule.scenario.onActivity {
            it.onBackPressedDispatcher.onBackPressed()
        }

        // 6. Returned to StartScreen
        composeTestRule.onNodeWithTag("StartScreen").assertIsDisplayed()
    }
}
