package com.google.bespoke

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.audio.ExoAudioPlayer
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.data.DeckRepository
import com.google.bespoke.data.ImportResult
import com.google.bespoke.data.ThemePreferences
import com.google.bespoke.model.DeckInfo
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.ui.LearningScreen
import com.google.bespoke.ui.StartScreen
import com.google.bespoke.ui.theme.BespokeTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

data class ActiveLearningSession(
    val reader: DatasetReader,
    val deckEngine: DeckEngine,
    val deckInfo: DeckInfo
)

class MainActivity : ComponentActivity() {

    private var audioPlayer: ExoAudioPlayer? = null
    private var refreshDecksCallback: (() -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                val trace = android.util.Log.getStackTraceString(throwable)
                val crashContent = "CRASH on thread ${thread.name}:\n$trace"
                val crashFileInternal = File(filesDir, "crash.log")
                crashFileInternal.writeText(crashContent, Charsets.UTF_8)
                getExternalFilesDir(null)?.let { extDir ->
                    File(extDir, "crash.log").writeText(crashContent, Charsets.UTF_8)
                }
                android.util.Log.e("BespokeCrash", "Uncaught exception", throwable)
            } catch (_: Exception) {}
            defaultHandler?.uncaughtException(thread, throwable)
        }

        val player = ExoAudioPlayer(this)
        audioPlayer = player

        setContent {
            val isSystemDark = isSystemInDarkTheme()
            var isDarkMode by remember {
                mutableStateOf(ThemePreferences.isDarkModeEnabled(this@MainActivity, isSystemDark))
            }

            var crashReportText by remember {
                val internal = File(filesDir, "crash.log")
                val ext = getExternalFilesDir(null)?.let { File(it, "crash.log") }
                val content = when {
                    internal.exists() -> internal.readText(Charsets.UTF_8)
                    ext?.exists() == true -> ext.readText(Charsets.UTF_8)
                    else -> null
                }
                mutableStateOf(content)
            }
            var isStartingSession by remember { mutableStateOf(false) }
            val coroutineScope = rememberCoroutineScope()

            BespokeTheme(darkTheme = isDarkMode) {
                var availableDecks by remember {
                    mutableStateOf(DeckRepository.listAvailableDecks(this@MainActivity))
                }
                LaunchedEffect(Unit) {
                    refreshDecksCallback = {
                        availableDecks = DeckRepository.listAvailableDecks(this@MainActivity)
                    }
                }
                var activeSession by remember { mutableStateOf<ActiveLearningSession?>(null) }

                if (crashReportText != null) {
                    AlertDialog(
                        onDismissRequest = {
                            try {
                                File(filesDir, "crash.log").delete()
                                getExternalFilesDir(null)?.let { File(it, "crash.log").delete() }
                            } catch (_: Exception) {}
                            crashReportText = null
                        },
                        title = { Text("App Crash Report") },
                        text = {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(max = 300.dp)
                                    .verticalScroll(rememberScrollState())
                            ) {
                                Text(
                                    text = crashReportText ?: "",
                                    fontSize = 12.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                        },
                        confirmButton = {
                            Button(
                                onClick = {
                                    val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                                    val clip = ClipData.newPlainText("Bespoke Crash", crashReportText)
                                    clipboard?.setPrimaryClip(clip)
                                    Toast.makeText(this@MainActivity, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                                }
                            ) {
                                Text("Copy")
                            }
                        },
                        dismissButton = {
                            TextButton(
                                onClick = {
                                    try {
                                        File(filesDir, "crash.log").delete()
                                        getExternalFilesDir(null)?.let { File(it, "crash.log").delete() }
                                    } catch (_: Exception) {}
                                    crashReportText = null
                                }
                            ) {
                                Text("Dismiss")
                            }
                        }
                    )
                }

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
                            coroutineScope.launch {
                                try {
                                    withContext(Dispatchers.IO) {
                                        DeckRepository.saveProgress(this@MainActivity, currentSession.deckEngine)
                                        try {
                                            currentSession.reader.close()
                                        } catch (_: Exception) {}
                                    }
                                    availableDecks = withContext(Dispatchers.IO) {
                                        DeckRepository.listAvailableDecks(this@MainActivity)
                                    }
                                } catch (e: Throwable) {
                                    val trace = android.util.Log.getStackTraceString(e)
                                    val errorMsg = "Failed on back navigation:\n$trace"
                                    crashReportText = errorMsg
                                    try {
                                        File(filesDir, "crash.log").writeText(errorMsg, Charsets.UTF_8)
                                        getExternalFilesDir(null)?.let { File(it, "crash.log").writeText(errorMsg, Charsets.UTF_8) }
                                    } catch (_: Exception) {}
                                } finally {
                                    activeSession = null
                                }
                            }
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
                        isLoading = isStartingSession,
                        onImportDeck = { uri ->
                            val result = DeckRepository.importDeckFromUri(this@MainActivity, uri)
                            if (result is ImportResult.Success) {
                                availableDecks = DeckRepository.listAvailableDecks(this@MainActivity)
                            }
                            result
                        },
                        onStartDeck = { deckInfo, difficulty, modes, assumeKnown ->
                            if (!isStartingSession) {
                                isStartingSession = true
                                coroutineScope.launch {
                                    try {
                                        withContext(Dispatchers.IO) {
                                            try {
                                                activeSession?.reader?.close()
                                            } catch (_: Exception) {}
                                        }
                                        val (reader, engine) = withContext(Dispatchers.IO) {
                                            DeckRepository.prepareDeck(
                                                this@MainActivity,
                                                deckInfo,
                                                difficulty,
                                                modes,
                                                assumeKnown
                                            )
                                        }
                                        activeSession = ActiveLearningSession(reader, engine, deckInfo)
                                    } catch (e: Throwable) {
                                        val trace = android.util.Log.getStackTraceString(e)
                                        val errorMsg = "Failed to open deck:\n$trace"
                                        crashReportText = errorMsg
                                        try {
                                            File(filesDir, "crash.log").writeText(errorMsg, Charsets.UTF_8)
                                            getExternalFilesDir(null)?.let { File(it, "crash.log").writeText(errorMsg, Charsets.UTF_8) }
                                        } catch (_: Exception) {}
                                    } finally {
                                        isStartingSession = false
                                    }
                                }
                            }
                        }
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshDecksCallback?.invoke()
    }

    override fun onDestroy() {
        super.onDestroy()
        audioPlayer?.release()
        audioPlayer = null
        refreshDecksCallback = null
    }
}
