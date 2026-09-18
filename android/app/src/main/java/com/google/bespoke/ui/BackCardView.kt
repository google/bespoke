package com.google.bespoke.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
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
    @Suppress("UNUSED_PARAMETER") mode: Mode,
    unitLookup: Map<String, UnitItem>,
    translations: Map<String, String>,
    ratings: Map<String, Int>,
    onRateWord: (unitId: String, score: Int) -> Unit,
    onAllSuccess: () -> Unit,
    onNext: (isReported: Boolean) -> Unit,
    onPlayAudio: (filename: String) -> Unit,
    modifier: Modifier = Modifier,
    isPlaying: Boolean = false,
    currentlyPlayingFile: String? = null,
    isUnitBlocked: (unitId: String) -> Boolean = { false },
    onToggleBlock: ((unitId: String, isBlocked: Boolean) -> Unit)? = null
) {
    val isDark = isDarkTheme()
    val subTextColor = if (isDark) TextGrayDark else TextGrayLight
    val readableTextColor = if (isDark) TextReadableDark else TextReadableLight

    val initialUnitId = card.unitIds().firstOrNull()
    var activeUnitId by remember(card.id) { mutableStateOf(initialUnitId) }
    var isCardBlocked by remember(card.id) { mutableStateOf(false) }
    var selectedDefinition by remember(card.id) {
        val initialDef = if (initialUnitId != null) {
            translations[initialUnitId] ?: unitLookup[initialUnitId]?.definition() ?: initialUnitId
        } else ""
        mutableStateOf(initialDef)
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag("BackCardView"),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp)
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
                            activeUnitId = tag.unit_id
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
                        onLongClick = {
                            activeUnitId = tag.unit_id
                            val definition = translations[tag.unit_id]
                                ?: unit?.definition()
                                ?: tag.unit_id
                            selectedDefinition = definition
                            val currentlyBlocked = isUnitBlocked(tag.unit_id)
                            onToggleBlock?.invoke(tag.unit_id, !currentlyBlocked)
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
                .testTag("DefinitionLabel")
        )

        HorizontalDivider()

        // 4. Controls: All Success, Block: Card switch, and Unit switch
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .testTag("ControlsRow"),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedButton(
                onClick = onAllSuccess,
                border = BorderStroke(1.dp, QuasarPositive),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = QuasarPositive),
                shape = RoundedCornerShape(8.dp),
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                modifier = Modifier.testTag("AllSuccessButton")
            ) {
                Text("All Success", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            }

            // Shared "Block:" label
            Text(
                text = "Block:",
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                color = subTextColor,
                modifier = Modifier.testTag("BlockSectionLabel")
            )

            // Middle: Card switch (Naturally wraps content without hardcoded width constraints)
            Row(
                modifier = Modifier
                    .wrapContentWidth()
                    .testTag("BlockCardContainer"),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Switch(
                    checked = isCardBlocked,
                    onCheckedChange = { isCardBlocked = it },
                    modifier = Modifier
                        .testTag("BlockCardSwitch")
                        .testTag("ReportErrorSwitch")
                        .scale(0.75f)
                )
                Text(
                    text = "Card",
                    fontSize = 12.sp,
                    color = subTextColor,
                    maxLines = 1,
                    softWrap = false,
                    modifier = Modifier.testTag("BlockCardLabel")
                )
            }

            // Right: Unit switch (Takes remaining space and truncates gracefully if too long)
            if (activeUnitId != null) {
                val unit = unitLookup[activeUnitId]
                val unitName = unit?.name() ?: activeUnitId!!
                val isBlocked = isUnitBlocked(activeUnitId!!)
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .testTag("BlockUnitContainer"),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Switch(
                        checked = isBlocked,
                        onCheckedChange = { checked ->
                            onToggleBlock?.invoke(activeUnitId!!, checked)
                        },
                        modifier = Modifier
                            .testTag("BlockUnitSwitch")
                            .scale(0.75f)
                    )
                    Text(
                        text = "'$unitName'",
                        fontSize = 12.sp,
                        color = subTextColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier
                            .weight(1f, fill = false)
                            .testTag("BlockUnitLabel")
                    )
                }
            } else {
                Spacer(modifier = Modifier.weight(1f))
            }
        }

        // 5. Next Button
        Button(
            onClick = { onNext(isCardBlocked) },
            modifier = Modifier
                .fillMaxWidth()
                .height(46.dp)
                .testTag("NextButton"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = PrimaryBlue,
                contentColor = Color.White
            )
        ) {
            Text(
                text = "Next",
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}
