package com.google.bespoke.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.model.DeckStats

@Composable
fun DeckStatsRow(
    stats: DeckStats,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .testTag("DeckStatsRow"),
        horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.CenterVertically
    ) {
        DeckBadge(label = "To Do: ${stats.waiting}", testTag = "BadgeToDo")
        Spacer(modifier = Modifier.width(8.dp))
        DeckBadge(label = "Known: ${stats.known}", testTag = "BadgeKnown")
        Spacer(modifier = Modifier.width(8.dp))
        DeckBadge(label = "Mature: ${stats.mature}", testTag = "BadgeMature")
    }
}

@Composable
fun DeckBadge(
    label: String,
    testTag: String = ""
) {
    Surface(
        modifier = if (testTag.isNotEmpty()) Modifier.testTag(testTag) else Modifier,
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, Color.Gray),
        color = Color.Transparent
    ) {
        Text(
            text = label,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium,
            color = Color.Gray
        )
    }
}
