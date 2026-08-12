package com.google.bespoke.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.model.Card
import com.google.bespoke.model.DeckStats
import com.google.bespoke.model.Mode
import com.google.bespoke.ui.components.*
import com.google.bespoke.ui.theme.PrimaryBlue
import com.google.bespoke.ui.theme.TextGrayDark
import com.google.bespoke.ui.theme.TextGrayLight
import com.google.bespoke.ui.theme.isDarkTheme

@Composable
fun FrontCardView(
    card: Card,
    mode: Mode,
    stats: DeckStats,
    onFlip: () -> Unit,
    onPlayAudio: (filename: String) -> Unit,
    isPlaying: Boolean = false,
    currentlyPlayingFile: String? = null,
    modifier: Modifier = Modifier
) {
    val isDark = isDarkTheme()
    val promptColor = if (isDark) TextGrayDark else TextGrayLight

    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag("FrontCardView"),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        when (mode) {
            Mode.LISTEN -> {
                AudioPlayerCard(
                    tracks = listOf(
                        AudioTrack(
                            label = "Play",
                            isPlaying = isPlaying && (currentlyPlayingFile == card.audio_filename || currentlyPlayingFile == null),
                            hasAudio = card.audio_filename.isNotEmpty(),
                            onPlay = { onPlayAudio(card.audio_filename) }
                        ),
                        AudioTrack(
                            label = "Slow",
                            isPlaying = isPlaying && currentlyPlayingFile == card.slow_audio_filename,
                            hasAudio = card.slow_audio_filename.isNotEmpty(),
                            onPlay = { onPlayAudio(card.slow_audio_filename) }
                        )
                    )
                )
            }

            Mode.SPEAK -> {
                Text(
                    text = "Speak the sentence!",
                    fontSize = 20.sp,
                    fontFamily = FontFamily.Monospace,
                    color = promptColor,
                    modifier = Modifier.testTag("PromptText")
                )
                if (card.native_audio_filename.isNotEmpty()) {
                    AudioPlayerCard(
                        tracks = listOf(
                            AudioTrack(
                                label = "",
                                isPlaying = isPlaying,
                                hasAudio = true,
                                onPlay = { onPlayAudio(card.native_audio_filename) }
                            )
                        )
                    )
                }
                SentenceCard(text = card.native_sentence, large = true)
            }

            Mode.READ -> {
                SentenceCard(text = card.sentence, large = true)
            }

            Mode.WRITE -> {
                Text(
                    text = "Write the sentence!",
                    fontSize = 20.sp,
                    fontFamily = FontFamily.Monospace,
                    color = promptColor,
                    modifier = Modifier.testTag("PromptText")
                )
                if (card.native_audio_filename.isNotEmpty()) {
                    AudioPlayerCard(
                        tracks = listOf(
                            AudioTrack(
                                label = "",
                                isPlaying = isPlaying,
                                hasAudio = true,
                                onPlay = { onPlayAudio(card.native_audio_filename) }
                            )
                        )
                    )
                }
                SentenceCard(text = card.native_sentence, large = true)
            }
        }

        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

        DeckStatsRow(stats = stats)

        Button(
            onClick = onFlip,
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp)
                .testTag("FlipButton"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = PrimaryBlue,
                contentColor = Color.White
            )
        ) {
            Text(
                text = "Flip",
                fontSize = 18.sp
            )
        }
    }
}
