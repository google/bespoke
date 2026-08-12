package com.google.bespoke.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.model.Card
import com.google.bespoke.model.Mode
import com.google.bespoke.model.UnitItem
import com.google.bespoke.ui.components.*
import com.google.bespoke.ui.theme.*

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun BackCardView(
    card: Card,
    mode: Mode,
    unitLookup: Map<String, UnitItem>,
    translations: Map<String, String>,
    ratings: Map<String, Int>,
    onRateWord: (unitId: String, score: Int) -> Unit,
    onAllSuccess: () -> Unit,
    onNext: (isReported: Boolean) -> Unit,
    onPlayAudio: (filename: String) -> Unit,
    isPlaying: Boolean = false,
    currentlyPlayingFile: String? = null,
    modifier: Modifier = Modifier
) {
    val isDark = isDarkTheme()
    val subTextColor = if (isDark) TextGrayDark else TextGrayLight
    val readableTextColor = if (isDark) TextReadableDark else TextReadableLight

    var isErrorReported by remember(card.id) { mutableStateOf(false) }
    var selectedDefinition by remember(card.id) { mutableStateOf("") }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag("BackCardView"),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        // 1. Playback Section (Horizontal neutral buttons: Play, Slow, Native)
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
                ),
                AudioTrack(
                    label = "Native",
                    isPlaying = isPlaying && currentlyPlayingFile == card.native_audio_filename,
                    hasAudio = card.native_audio_filename.isNotEmpty(),
                    onPlay = { onPlayAudio(card.native_audio_filename) }
                )
            )
        )

        // 2. Text Section
        SentenceCard(text = card.sentence, large = true)

        if (!card.phonetic.isNullOrEmpty()) {
            Text(
                text = card.phonetic,
                fontSize = 20.sp,
                fontFamily = FontFamily.Monospace,
                color = subTextColor,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("PhoneticText")
            )
        }

        SentenceCard(text = card.native_sentence, large = false)

        // 3. Rating Section
        Text(
            text = "Rate specific words:",
            fontSize = 14.sp,
            color = subTextColor,
            modifier = Modifier
                .align(Alignment.Start)
                .testTag("RateWordsHeader")
        )

        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .testTag("WordRatingButtonsRow"),
            horizontalArrangement = Arrangement.Center,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            for (tag in card.splitIntoParts()) {
                if (tag.unit_id.isEmpty()) {
                    Text(
                        text = tag.occurance,
                        fontSize = 18.sp,
                        color = readableTextColor,
                        modifier = Modifier
                            .align(Alignment.CenterVertically)
                            .padding(horizontal = 4.dp, vertical = 8.dp)
                    )
                } else {
                    val currentRating = ratings[tag.unit_id] ?: 0
                    val unit = unitLookup[tag.unit_id]
                    val unitName = unit?.name() ?: tag.unit_id

                    WordRatingButton(
                        word = tag.occurance,
                        subCaption = unitName,
                        ratingScore = currentRating,
                        onClick = {
                            val nextScore = when (currentRating) {
                                0 -> 3
                                3 -> 1
                                1 -> 0
                                else -> 0
                            }
                            onRateWord(tag.unit_id, nextScore)

                            val definition = translations[tag.unit_id]
                                ?: unit?.definition()
                                ?: tag.unit_id
                            selectedDefinition = definition
                        },
                        modifier = Modifier.padding(horizontal = 2.dp)
                    )
                }
            }
        }

        // Definition display label
        Text(
            text = selectedDefinition,
            fontSize = 14.sp,
            color = readableTextColor,
            textAlign = TextAlign.Center,
            minLines = 1,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 24.dp)
                .padding(vertical = 4.dp)
                .testTag("DefinitionLabel")
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

        // 4. Controls: All Success & Report Error
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedButton(
                onClick = onAllSuccess,
                border = BorderStroke(1.dp, QuasarPositive),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = QuasarPositive),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.testTag("AllSuccessButton")
            ) {
                Text("All Success", fontWeight = FontWeight.SemiBold)
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Switch(
                    checked = isErrorReported,
                    onCheckedChange = { isErrorReported = it },
                    modifier = Modifier.testTag("ReportErrorSwitch")
                )
                Text(
                    text = "Report Error",
                    fontSize = 14.sp,
                    color = subTextColor
                )
            }
        }

        // 5. Next Button
        Button(
            onClick = { onNext(isErrorReported) },
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp)
                .testTag("NextButton"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = PrimaryBlue,
                contentColor = Color.White
            )
        ) {
            Text(
                text = "Next",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}
