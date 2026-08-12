package com.google.bespoke.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.ui.theme.SentenceCardBgDark
import com.google.bespoke.ui.theme.SentenceCardBgLight
import com.google.bespoke.ui.theme.TextReadableDark
import com.google.bespoke.ui.theme.TextReadableLight
import com.google.bespoke.ui.theme.isDarkTheme

@Composable
fun SentenceCard(
    text: String,
    large: Boolean = true,
    modifier: Modifier = Modifier,
    testTag: String = if (large) "LargeSentence" else "SmallSentence"
) {
    val isDark = isDarkTheme()
    val bgColor = if (isDark) SentenceCardBgDark else SentenceCardBgLight
    val textColor = if (isDark) TextReadableDark else TextReadableLight
    val fontSize = if (large) 26.sp else 18.sp
    val padding = if (large) 20.dp else 12.dp

    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag(testTag),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = bgColor),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(padding),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = text,
                fontSize = fontSize,
                fontFamily = FontFamily.SansSerif,
                textAlign = TextAlign.Center,
                color = textColor
            )
        }
    }
}
