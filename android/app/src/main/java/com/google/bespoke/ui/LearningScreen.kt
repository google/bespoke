package com.google.bespoke.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.key.*
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.audio.AudioPlayer
import com.google.bespoke.audio.ExoAudioPlayer
import com.google.bespoke.data.DatasetReader
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import com.google.bespoke.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun LearningScreen(
    deckEngine: DeckEngine,
    datasetReader: DatasetReader,
    audioPlayer: AudioPlayer,
    onSaveProgress: (() -> Unit)? = null,
    onNavigateBack: (() -> Unit)? = null,
    deckTitle: String? = null,
    modifier: Modifier = Modifier
) {
    if (onNavigateBack != null) {
        BackHandler(enabled = true) {
            onSaveProgress?.invoke()
            onNavigateBack()
        }
    }

    var currentMode by remember { mutableStateOf(Mode.LISTEN) }
    var currentCard by remember {
        mutableStateOf(
            Card(
                id = "",
                sentence = "",
                native_sentence = "",
                audio_filename = "",
                slow_audio_filename = "",
                native_audio_filename = "",
                phonetic = null,
                unit_tags = emptyList(),
                notes = emptyList()
            )
        )
    }
    var isOnBack by remember { mutableStateOf(false) }
    var isPlaying by remember { mutableStateOf(false) }
    var currentlyPlayingFile by remember { mutableStateOf<String?>(null) }
    var stats by remember { mutableStateOf(DeckStats(0, 0, 0)) }
    val ratings = remember { mutableStateMapOf<String, Int>() }

    val coroutineScope = rememberCoroutineScope()

    fun playAudioFile(filename: String) {
        if (filename.isEmpty()) return
        isPlaying = true
        currentlyPlayingFile = filename
        coroutineScope.launch {
            val blob = withContext(Dispatchers.IO) {
                datasetReader.getAudioBlob(filename)
            }
            if (blob != null && blob.isNotEmpty()) {
                audioPlayer.playBytes(blob) {
                    isPlaying = false
                    if (currentlyPlayingFile == filename) {
                        currentlyPlayingFile = null
                    }
                }
            } else {
                audioPlayer.playFile(filename) {
                    isPlaying = false
                    if (currentlyPlayingFile == filename) {
                        currentlyPlayingFile = null
                    }
                }
            }
        }
    }

    fun loadNextCard() {
        coroutineScope.launch {
            try {
                audioPlayer.stop()
                isPlaying = false
                currentlyPlayingFile = null

                val (mode, card) = withContext(Dispatchers.IO) {
                    deckEngine.draw()
                }
                currentMode = mode
                currentCard = card
                isOnBack = false
                stats = deckEngine.stats()
                ratings.clear()
                for (uid in card.unitIds()) {
                    ratings[uid] = 0
                }

                // Autoplay in LISTEN mode on front view
                if (mode == Mode.LISTEN && card.audio_filename.isNotEmpty()) {
                    playAudioFile(card.audio_filename)
                }
            } catch (e: Exception) {
                android.util.Log.e("LearningScreen", "Error loading card", e)
            }
        }
    }

    // Initial load
    LaunchedEffect(deckEngine) {
        loadNextCard()
    }

    fun flipCard() {
        isOnBack = true
        // Autoplay target audio in back view if not Mode.LISTEN
        if (currentMode != Mode.LISTEN && currentCard.audio_filename.isNotEmpty()) {
            playAudioFile(currentCard.audio_filename)
        }
    }

    fun finalizeCard(isReported: Boolean) {
        for ((unitId, score) in ratings) {
            val unit = deckEngine.unitLookup[unitId] ?: WordUnit(unitId, Difficulty.A1)
            deckEngine.rate(unit, currentMode, score)
        }
        deckEngine.logUsage(currentCard.id, isReported = isReported)
        stats = deckEngine.stats()
        onSaveProgress?.invoke()
        loadNextCard()
    }

    Scaffold(
        modifier = modifier
            .fillMaxSize()
            .testTag("LearningScreen")
            .onKeyEvent { keyEvent ->
                if (keyEvent.type == KeyEventType.KeyDown) {
                    when (keyEvent.key) {
                        Key.One -> {
                            if (!isOnBack) {
                                if (currentMode == Mode.LISTEN) playAudioFile(currentCard.audio_filename)
                                else if (currentMode == Mode.SPEAK || currentMode == Mode.WRITE) playAudioFile(currentCard.native_audio_filename)
                            } else {
                                playAudioFile(currentCard.audio_filename)
                            }
                            true
                        }
                        Key.Two -> {
                            playAudioFile(currentCard.slow_audio_filename)
                            true
                        }
                        Key.Three -> {
                            if (isOnBack) {
                                playAudioFile(currentCard.native_audio_filename)
                            }
                            true
                        }
                        Key.Spacebar -> {
                            if (isOnBack) {
                                isOnBack = false
                            } else {
                                flipCard()
                            }
                            true
                        }
                        else -> false
                    }
                } else {
                    false
                }
            }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentAlignment = Alignment.TopCenter
        ) {
            Column(
                modifier = Modifier
                    .widthIn(max = 672.dp)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp)
                    .verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                if (currentCard.id.isNotEmpty()) {
                    if (!isOnBack) {
                        FrontCardView(
                            card = currentCard,
                            mode = currentMode,
                            stats = stats,
                            onFlip = { flipCard() },
                            onPlayAudio = { playAudioFile(it) },
                            isPlaying = isPlaying,
                            currentlyPlayingFile = currentlyPlayingFile
                        )
                    } else {
                        BackCardView(
                            card = currentCard,
                            mode = currentMode,
                            unitLookup = deckEngine.unitLookup,
                            translations = deckEngine.translations,
                            ratings = ratings,
                            onRateWord = { unitId, score ->
                                ratings[unitId] = score
                            },
                            onAllSuccess = {
                                for (uid in currentCard.unitIds()) {
                                    ratings[uid] = 3
                                }
                            },
                            onNext = { isReported ->
                                finalizeCard(isReported)
                            },
                            onPlayAudio = { playAudioFile(it) },
                            isPlaying = isPlaying,
                            currentlyPlayingFile = currentlyPlayingFile
                        )
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(300.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            CircularProgressIndicator()
                            Text(
                                text = "Loading card...",
                                fontSize = 16.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }
        }
    }
}
