package com.charonsecurity.homora.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * One dark look, as in the design: near-black glass surfaces, white as the
 * accent, the logo's blue for brand moments, and colour otherwise reserved
 * for meaning (amber = worth fixing, red = fix soon, green = passed).
 */
object Brand {
    val Blue = Color(0xFF2E8BFF)
    val Cyan = Color(0xFF45C9FF)
    val DeepBlue = Color(0xFF0B1630)
    val Ink = Color(0xFF05070B)
    val Glow = Color(0xFFFFFFFF)
}

private val Scheme = darkColorScheme(
    primary = Color(0xFFF4F6FA),
    onPrimary = Color(0xFF0A0D12),
    primaryContainer = Color(0xFF232A35),
    onPrimaryContainer = Color(0xFFF4F6FA),
    secondary = Color(0xFFB9C1CC),
    onSecondary = Color(0xFF14181E),
    secondaryContainer = Color(0xFF1E242C),
    onSecondaryContainer = Color(0xFFE3E7ED),
    tertiary = Brand.Blue,
    onTertiary = Color.White,
    background = Brand.Ink,
    onBackground = Color(0xFFF2F4F7),
    surface = Brand.Ink,
    onSurface = Color(0xFFF2F4F7),
    surfaceVariant = Color(0xFF1A1F26),
    onSurfaceVariant = Color(0xFF98A1AD),
    surfaceContainerLowest = Color(0xFF040508),
    surfaceContainerLow = Color(0xFF0E1116),
    surfaceContainer = Color(0xFF13171D),
    surfaceContainerHigh = Color(0xFF191E25),
    surfaceContainerHighest = Color(0xFF222832),
    surfaceBright = Color(0xFF2A313B),
    outline = Color(0xFF5B6470),
    outlineVariant = Color(0xFF242A33),
    error = Color(0xFFFF8A80),
    onError = Color(0xFF2B0A08),
    scrim = Color(0xCC000000),
)

private val AppTypography = Typography().let { t ->
    t.copy(
        displaySmall = t.displaySmall.copy(fontWeight = FontWeight.SemiBold),
        headlineLarge = t.headlineLarge.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.5).sp),
        headlineMedium = t.headlineMedium.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.3).sp),
        headlineSmall = t.headlineSmall.copy(fontWeight = FontWeight.SemiBold),
        titleLarge = t.titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = t.titleMedium.copy(fontWeight = FontWeight.Medium),
    )
}

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

/** Severity colours, kept outside Material's scheme so their meaning stays fixed. */
@Immutable
data class StatusColors(val high: Color, val medium: Color, val good: Color, val onStatus: Color)

private val Status = StatusColors(high = Color(0xFFFF7A70), medium = Color(0xFFFFC266), good = Color(0xFF6EE7A0), onStatus = Color(0xFF0A0D12))

val LocalStatusColors = staticCompositionLocalOf { Status }

@Composable
fun HomoraTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalStatusColors provides Status) {
        MaterialTheme(colorScheme = Scheme, typography = AppTypography, shapes = AppShapes, content = content)
    }
}
