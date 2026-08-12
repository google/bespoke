package com.google.bespoke.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.ui.theme.*

data class AudioTrack(
    val label: String,
    val isPlaying: Boolean = false,
    val hasAudio: Boolean = true,
    val onPlay: () -> Unit
)

@Composable
fun AudioPlayerCard(
    tracks: List<AudioTrack>,
    modifier: Modifier = Modifier
) {
    val isDark = isDarkTheme()
    val cardBg = if (isDark) AudioBoxBgDark else AudioBoxBgLight

    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag("AudioPlayerCard"),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = cardBg)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
            verticalAlignment = Alignment.CenterVertically
        ) {
            for (track in tracks) {
                AudioTrackChip(track = track)
            }
        }
    }
}

@Composable
fun AudioTrackChip(
    track: AudioTrack,
    modifier: Modifier = Modifier
) {
    val isDark = isDarkTheme()
    // Neutral color scheme (Zinc palette) avoiding semantic colors (blue/green/red)
    val neutralContainer = if (isDark) Color(0xFF3F3F46) else Color(0xFFE4E4E7)
    val playingContainer = if (isDark) Color(0xFF52525B) else Color(0xFFD4D4D8)
    val neutralContent = if (isDark) Color(0xFFF4F4F5) else Color(0xFF18181B)
    val tagSuffix = track.label.replace(":", "").trim().ifEmpty { "Main" }

    if (track.hasAudio) {
        FilledTonalButton(
            onClick = track.onPlay,
            modifier = modifier
                .height(42.dp)
                .testTag("AudioBtn_$tagSuffix"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.filledTonalButtonColors(
                containerColor = if (track.isPlaying) playingContainer else neutralContainer,
                contentColor = neutralContent
            ),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
        ) {
            Icon(
                imageVector = if (track.isPlaying) Icons.Default.Stop else Icons.AutoMirrored.Filled.VolumeUp,
                contentDescription = if (track.label.isNotEmpty()) "Play ${track.label}" else "Play audio",
                modifier = Modifier.size(18.dp)
            )
            if (track.label.isNotEmpty()) {
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = track.label,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    } else {
        FilledTonalButton(
            onClick = {},
            enabled = false,
            modifier = modifier
                .height(42.dp)
                .testTag("AudioMissing_$tagSuffix"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.filledTonalButtonColors(
                disabledContainerColor = if (isDark) Color(0xFF27272A) else Color(0xFFF4F4F5),
                disabledContentColor = Color.Gray
            ),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.VolumeOff,
                contentDescription = "Audio unavailable",
                modifier = Modifier.size(18.dp)
            )
            if (track.label.isNotEmpty()) {
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = track.label,
                    fontSize = 14.sp,
                    color = Color.Gray
                )
            }
        }
    }
}
