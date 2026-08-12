package com.google.bespoke.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf

val LocalDarkTheme = staticCompositionLocalOf { false }

@Composable
fun isDarkTheme(): Boolean = LocalDarkTheme.current

private val DarkColorScheme = darkColorScheme(
    primary = PrimaryBlue,
    secondary = QuasarPositive,
    tertiary = QuasarInfo,
    background = BgDark,
    surface = CardBgDark,
    surfaceVariant = SentenceCardBgDark,
    onBackground = TextReadableDark,
    onSurface = TextReadableDark,
    onSurfaceVariant = TextGrayDark
)

private val LightColorScheme = lightColorScheme(
    primary = PrimaryBlue,
    secondary = QuasarPositive,
    tertiary = QuasarInfo,
    background = BgLight,
    surface = CardBgLight,
    surfaceVariant = AudioBoxBgLight,
    onBackground = TextReadableLight,
    onSurface = TextReadableLight,
    onSurfaceVariant = TextGrayLight
)

@Composable
fun BespokeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    CompositionLocalProvider(LocalDarkTheme provides darkTheme) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = Typography,
            content = content
        )
    }
}
