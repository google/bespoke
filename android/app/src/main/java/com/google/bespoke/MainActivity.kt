package com.google.bespoke

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import com.google.bespoke.audio.ExoAudioPlayer
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.data.DeckRepository
import com.google.bespoke.data.ImportResult
import com.google.bespoke.model.DeckInfo
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.ui.LearningScreen
import com.google.bespoke.ui.StartScreen
import com.google.bespoke.ui.theme.BespokeTheme

import androidx.compose.foundation.isSystemInDarkTheme
import com.google.bespoke.data.ThemePreferences

data class ActiveLearningSession(
    val reader: DatasetReader,
    val deckEngine: DeckEngine,
    val deckInfo: DeckInfo
)

class MainActivity : ComponentActivity() {

    private var audioPlayer: ExoAudioPlayer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val player = ExoAudioPlayer(this)
        audioPlayer = player

        setContent {
            val isSystemDark = isSystemInDarkTheme()
            var isDarkMode by remember {
                mutableStateOf(ThemePreferences.isDarkModeEnabled(this@MainActivity, isSystemDark))
            }

            BespokeTheme(darkTheme = isDarkMode) {
                var availableDecks by remember {
                    mutableStateOf(DeckRepository.listAvailableDecks(this@MainActivity))
                }
                var activeSession by remember { mutableStateOf<ActiveLearningSession?>(null) }

                val currentSession = activeSession
                if (currentSession != null) {
                    LearningScreen(
                        deckEngine = currentSession.deckEngine,
                        datasetReader = currentSession.reader,
                        audioPlayer = player,
                        deckTitle = currentSession.deckInfo.targetLanguage.replaceFirstChar { it.uppercase() },
                        onSaveProgress = {
                            DeckRepository.saveProgress(this@MainActivity, currentSession.deckEngine)
                        },
                        onNavigateBack = {
                            DeckRepository.saveProgress(this@MainActivity, currentSession.deckEngine)
                            availableDecks = DeckRepository.listAvailableDecks(this@MainActivity)
                            activeSession = null
                        }
                    )
                } else {
                    StartScreen(
                        isDarkMode = isDarkMode,
                        onToggleDarkMode = { enabled ->
                            isDarkMode = enabled
                            ThemePreferences.setDarkModeEnabled(this@MainActivity, enabled)
                        },
                        availableDecks = availableDecks,
                        onImportDeck = { uri ->
                            val result = DeckRepository.importDeckFromUri(this@MainActivity, uri)
                            if (result is ImportResult.Success) {
                                availableDecks = DeckRepository.listAvailableDecks(this@MainActivity)
                            }
                            result
                        },
                        onStartDeck = { deckInfo, difficulty, modes, assumeKnown ->
                            val (reader, engine) = DeckRepository.prepareDeck(
                                this@MainActivity,
                                deckInfo,
                                difficulty,
                                modes,
                                assumeKnown
                            )
                            activeSession = ActiveLearningSession(reader, engine, deckInfo)
                        }
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        audioPlayer?.release()
        audioPlayer = null
    }
}
