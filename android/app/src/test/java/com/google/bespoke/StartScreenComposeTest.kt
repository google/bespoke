package com.google.bespoke

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.google.bespoke.model.DeckInfo
import com.google.bespoke.model.DeckStats
import com.google.bespoke.model.Difficulty
import com.google.bespoke.model.Mode
import com.google.bespoke.ui.StartScreen
import com.google.bespoke.ui.theme.BespokeTheme
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class StartScreenComposeTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun testStartScreenElementsAndOptionSelection() {
        val sampleDeck = DeckInfo(
            id = "sample_deck.db",
            title = "English -> Japanese (Sample Deck)",
            targetLanguage = "Japanese",
            nativeLanguage = "English",
            file = null,
            cardCount = 10,
            vocabCount = 8,
            savedStats = DeckStats(waiting = 3, known = 4, mature = 1),
            savedDifficulty = Difficulty.A1
        )

        var startedDeck: DeckInfo? = null
        var startedDifficulty: Difficulty? = null
        var startedModes: List<Mode>? = null
        var startedAssumeKnown: Difficulty? = null

        composeTestRule.setContent {
            BespokeTheme {
                StartScreen(
                    availableDecks = listOf(sampleDeck),
                    onStartDeck = { deck, diff, modes, assume ->
                        startedDeck = deck
                        startedDifficulty = diff
                        startedModes = modes
                        startedAssumeKnown = assume
                    }
                )
            }
        }

        // 1. Verify App Title & Deck Selection Card
        composeTestRule.onNodeWithTag("AppTitle").assertIsDisplayed()
        composeTestRule.onNodeWithTag("DeckSelectionCard").assertIsDisplayed()
        composeTestRule.onNodeWithText("English -> Japanese (Sample Deck)").assertIsDisplayed()


        // 2. Verify Difficulty Card and select A2
        composeTestRule.onNodeWithTag("DifficultyCard").performScrollTo().assertIsDisplayed()
        composeTestRule.onNodeWithTag("DifficultyChip_A2").performScrollTo().performClick()

        // 3. Verify Mode chips and toggle Read & Write modes
        composeTestRule.onNodeWithTag("ModesCard").performScrollTo().assertIsDisplayed()
        composeTestRule.onNodeWithTag("ModeChip_Read").performScrollTo().performClick()
        composeTestRule.onNodeWithTag("ModeChip_Write").performScrollTo().performClick()

        // 4. Click Start/Continue button
        composeTestRule.onNodeWithTag("StartLearningButton").performScrollTo().performClick()

        // 5. Assert callback received configured values
        assertNotNull(startedDeck)
        assertEquals("sample_deck.db", startedDeck!!.id)
        assertEquals(Difficulty.A2, startedDifficulty)
        assertNotNull(startedModes)
        assertTrue(startedModes!!.contains(Mode.LISTEN))
        assertTrue(startedModes!!.contains(Mode.SPEAK))
        assertTrue(startedModes!!.contains(Mode.READ))
        assertTrue(startedModes!!.contains(Mode.WRITE))
        assertNull(startedAssumeKnown)
    }

    @Test
    fun testNavigationBackAndDeckSwitching() {
        val deck1 = DeckInfo(
            id = "deck1.db",
            title = "English -> Japanese (Deck 1)",
            targetLanguage = "Japanese",
            nativeLanguage = "English",
            file = null,
            cardCount = 5,
            vocabCount = 4
        )
        val deck2 = DeckInfo(
            id = "deck2.db",
            title = "English -> German (Deck 2)",
            targetLanguage = "German",
            nativeLanguage = "English",
            file = null,
            cardCount = 20,
            vocabCount = 15
        )

        var startedDeck: DeckInfo? = null

        composeTestRule.setContent {
            BespokeTheme {
                StartScreen(
                    availableDecks = listOf(deck1, deck2),
                    onStartDeck = { deck, _, _, _ ->
                        startedDeck = deck
                    }
                )
            }
        }

        // Open dropdown and select second deck
        composeTestRule.onNodeWithTag("DeckSelectorTextField").performScrollTo().performClick()
        composeTestRule.onNodeWithTag("DeckOption_1").performClick()

        // Click Start
        composeTestRule.onNodeWithTag("StartLearningButton").performScrollTo().performClick()
        assertNotNull(startedDeck)
        assertEquals("deck2.db", startedDeck!!.id)
    }
}
