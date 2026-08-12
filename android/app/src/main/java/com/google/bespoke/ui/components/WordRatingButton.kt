package com.google.bespoke.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.ui.theme.*

fun getRatingColor(score: Int): Color {
    return when (score) {
        3 -> QuasarPositive
        1 -> QuasarNegative
        2 -> QuasarWarning
        0 -> QuasarInfo
        else -> QuasarInfo
    }
}

fun getNextRating(currentScore: Int): Int {
    return when (currentScore) {
        0 -> 3
        3 -> 1
        1 -> 0
        2 -> 1
        else -> 0
    }
}

@Composable
fun WordRatingButton(
    word: String,
    subCaption: String,
    ratingScore: Int,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    testTag: String = "WordButton_$word"
) {
    val isDark = isDarkTheme()
    val captionColor = if (isDark) TextGrayDark else TextGrayLight
    val buttonBgColor = getRatingColor(ratingScore)

    Column(
        modifier = modifier.padding(2.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Button(
            onClick = onClick,
            modifier = Modifier
                .testTag(testTag)
                .height(44.dp),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = buttonBgColor,
                contentColor = Color.White
            ),
            elevation = ButtonDefaults.buttonElevation(
                defaultElevation = 3.dp,
                pressedElevation = 6.dp
            ),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
        ) {
            Text(
                text = word,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center
            )
        }

        if (subCaption.isNotEmpty()) {
            Text(
                text = subCaption,
                fontSize = 10.sp,
                color = captionColor,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
    }
}
