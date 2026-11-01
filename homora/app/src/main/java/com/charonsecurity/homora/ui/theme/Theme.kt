package com.charonsecurity.homora.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Deliberately plain: one blue accent from the icon, neutral surfaces, and
 * colour used only where it means something (amber = worth fixing, red = fix soon).
 */
private val Light = lightColorScheme(
    primary = Color(0xFF1F6FE5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE7FB),
    onPrimaryContainer = Color(0xFF0B2A5C),
    secondary = Color(0xFF52606F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3E8EF),
    onSecondaryContainer = Color(0xFF1C2530),
    background = Color(0xFFF8F9FC),
    onBackground = Color(0xFF171B21),
    surface = Color(0xFFF8F9FC),
    onSurface = Color(0xFF171B21),
    surfaceVariant = Color(0xFFE6E9EF),
    onSurfaceVariant = Color(0xFF4A5260),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF2F4F8),
    surfaceContainer = Color(0xFFECEFF4),
    surfaceContainerHigh = Color(0xFFE6E9EF),
    surfaceContainerHighest = Color(0xFFE0E4EB),
    outline = Color(0xFF7A8290),
    outlineVariant = Color(0xFFCDD2DA),
    error = Color(0xFFC62828),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF8DB6FF),
    onPrimary = Color(0xFF062B66),
    primaryContainer = Color(0xFF16407F),
    onPrimaryContainer = Color(0xFFDCE7FB),
    secondary = Color(0xFFB7C2D0),
    onSecondary = Color(0xFF223040),
    secondaryContainer = Color(0xFF2E3946),
    onSecondaryContainer = Color(0xFFDCE3EC),
    background = Color(0xFF101318),
    onBackground = Color(0xFFE2E5EA),
    surface = Color(0xFF101318),
    onSurface = Color(0xFFE2E5EA),
    surfaceVariant = Color(0xFF2B3038),
    onSurfaceVariant = Color(0xFFB9C0CB),
    surfaceContainerLowest = Color(0xFF0B0E12),
    surfaceContainerLow = Color(0xFF171B21),
    surfaceContainer = Color(0xFF1C2027),
    surfaceContainerHigh = Color(0xFF242932),
    surfaceContainerHighest = Color(0xFF2E343D),
    outline = Color(0xFF8B93A0),
    outlineVariant = Color(0xFF3B424C),
    error = Color(0xFFFF8A80),
)

/** Severity colours, kept outside Material's scheme so their meaning stays fixed. */
@Immutable
data class StatusColors(val high: Color, val medium: Color, val good: Color, val onStatus: Color)

private val LightStatus = StatusColors(high = Color(0xFFC62828), medium = Color(0xFFB26A00), good = Color(0xFF2E7D32), onStatus = Color.White)
private val DarkStatus = StatusColors(high = Color(0xFFFF8A80), medium = Color(0xFFFFC266), good = Color(0xFF81C784), onStatus = Color(0xFF101318))

val LocalStatusColors = staticCompositionLocalOf { LightStatus }

@Composable
fun HomoraTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    androidx.compose.runtime.CompositionLocalProvider(LocalStatusColors provides if (dark) DarkStatus else LightStatus) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
    }
}
