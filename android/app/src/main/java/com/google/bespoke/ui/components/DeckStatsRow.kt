package com.google.bespoke.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.google.bespoke.model.DeckStats
import com.google.bespoke.ui.theme.*

@Composable
fun DeckStatsRow(
    stats: DeckStats,
    modifier: Modifier = Modifier,
    blockedCount: Int = 0,
    onBlockedClick: (() -> Unit)? = null
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
        if (blockedCount > 0 || onBlockedClick != null) {
            Spacer(modifier = Modifier.width(8.dp))
            DeckBadge(
                label = "Blocked: $blockedCount",
                testTag = "BadgeBlocked",
                onClick = onBlockedClick
            )
        }
    }
}

@Composable
fun DeckBadge(
    label: String,
    testTag: String = "",
    onClick: (() -> Unit)? = null
) {
    val clickableModifier = if (onClick != null) Modifier.clickable { onClick() } else Modifier
    Surface(
        modifier = (if (testTag.isNotEmpty()) Modifier.testTag(testTag) else Modifier)
            .then(clickableModifier),
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

data class BlockedUnitDisplay(
    val unitId: String,
    val name: String,
    val definition: String
)

@Composable
fun BlockedUnitsDialog(
    blockedUnits: List<BlockedUnitDisplay>,
    onDismiss: () -> Unit,
    onUnblockUnit: (String) -> Unit
) {
    val isDark = isDarkTheme()
    val cardBg = if (isDark) CardBgDark else CardBgLight
    val textColor = if (isDark) TextReadableDark else TextReadableLight
    val subTextColor = if (isDark) TextGrayDark else TextGrayLight

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .heightIn(max = 560.dp)
                .testTag("BlockedUnitsDialog"),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = cardBg)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Blocked Units",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = textColor
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.testTag("CloseBlockedDialogButton")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = textColor
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                if (blockedUnits.isEmpty()) {
                    Text(
                        text = "No blocked units.",
                        fontSize = 14.sp,
                        color = subTextColor,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 24.dp)
                            .testTag("NoBlockedUnitsText"),
                        textAlign = TextAlign.Center
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f, fill = false)
                            .testTag("BlockedUnitsList"),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(blockedUnits, key = { it.unitId }) { item ->
                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag("BlockedUnitItem_${item.unitId}"),
                                shape = RoundedCornerShape(8.dp),
                                color = if (isDark) Color(0xFF3F3F46) else Color(0xFFF4F4F5)
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 12.dp, vertical = 8.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = item.name,
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = textColor
                                        )
                                        if (item.definition.isNotEmpty()) {
                                            Text(
                                                text = item.definition,
                                                fontSize = 12.sp,
                                                color = subTextColor
                                            )
                                        }
                                    }
                                    IconButton(
                                        onClick = { onUnblockUnit(item.unitId) },
                                        modifier = Modifier
                                            .size(36.dp)
                                            .testTag("UnblockButton_${item.unitId}")
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Close,
                                            contentDescription = "Unblock ${item.name}",
                                            tint = MutedRed,
                                            modifier = Modifier.size(18.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
