package com.charonsecurity.homora.ui.onboarding

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.Lightbulb
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.QuestionMark
import androidx.compose.material.icons.outlined.Router
import androidx.compose.material.icons.outlined.SmartDisplay
import androidx.compose.material.icons.outlined.Smartphone
import androidx.compose.material.icons.outlined.Speaker
import androidx.compose.material.icons.outlined.Thermostat
import androidx.compose.material.icons.outlined.Videocam
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.ui.components.HomoraLogo
import com.charonsecurity.homora.ui.theme.Brand
import com.charonsecurity.homora.ui.theme.LocalStatusColors
import kotlin.math.cos
import kotlin.math.sin

/*
 * Animated line-art for the intro pages: white strokes with the logo's blue
 * as the accent. All loops use infinite transitions, which pause in tests and
 * stop when the page leaves the screen.
 */

private val Line = Color.White
private val Faint = Color.White.copy(alpha = 0.12f)
private val ArtSize = 280.dp

/** A small glass bubble holding an icon. */
@Composable
private fun Bubble(icon: ImageVector, modifier: Modifier = Modifier, size: Dp = 44.dp, tint: Color = Line) {
    Box(
        modifier
            .size(size)
            .background(Color(0xFF12161C), CircleShape)
            .border(1.dp, Color.White.copy(alpha = 0.16f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, Modifier.size(size * 0.5f), tint = tint)
    }
}

private data class Blip(val angle: Float, val radius: Float, val icon: ImageVector, val unknown: Boolean = false)

private val BLIPS = listOf(
    Blip(-120f, 0.78f, Icons.Outlined.SmartDisplay),
    Blip(-40f, 0.62f, Icons.Outlined.Videocam),
    Blip(25f, 0.84f, Icons.Outlined.Computer),
    Blip(110f, 0.70f, Icons.Outlined.Smartphone),
    Blip(170f, 0.55f, Icons.Outlined.QuestionMark, unknown = true),
)

/** Page 1: a radar sweep that "finds" devices as it passes them. */
@Composable
fun RadarIllustration(modifier: Modifier = Modifier) {
    val t = rememberInfiniteTransition(label = "radar")
    val sweep by t.animateFloat(0f, 360f, infiniteRepeatable(tween(3600, easing = LinearEasing)), label = "sweep")
    val amber = LocalStatusColors.current.medium
    Box(modifier.size(ArtSize), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val c = center
            val r = size.minDimension / 2f
            listOf(0.33f, 0.66f, 1f).forEach { drawCircle(Faint, r * it - 2f, c, style = Stroke(1.5f)) }
            drawLine(Faint, Offset(c.x - r, c.y), Offset(c.x + r, c.y), 1f)
            drawLine(Faint, Offset(c.x, c.y - r), Offset(c.x, c.y + r), 1f)
            rotate(sweep, c) {
                drawArc(
                    brush = Brush.sweepGradient(0f to Color.Transparent, 0.80f to Color.Transparent, 1f to Brand.Blue.copy(alpha = 0.45f), center = c),
                    startAngle = 290f, sweepAngle = 70f, useCenter = true,
                    topLeft = Offset(c.x - r, c.y - r), size = Size(r * 2, r * 2),
                )
                drawLine(Brand.Cyan, c, Offset(c.x + r, c.y), 3f, StrokeCap.Round)
            }
        }
        val half = ArtSize / 2
        BLIPS.forEach { b ->
            // Bright just after the sweep passes, then fades until the next pass.
            val since = ((sweep - b.angle) % 360f + 360f) % 360f / 360f
            val glow = (1f - since).let { it * it }
            val rad = Math.toRadians(b.angle.toDouble())
            val dx = (cos(rad) * b.radius * (half.value - 22)).toFloat()
            val dy = (sin(rad) * b.radius * (half.value - 22)).toFloat()
            Bubble(
                b.icon,
                Modifier.offset(dx.dp, dy.dp).graphicsLayer {
                    alpha = 0.35f + 0.65f * glow
                    val s = 0.9f + 0.15f * glow
                    scaleX = s; scaleY = s
                },
                size = 42.dp,
                tint = if (b.unknown) amber else Line,
            )
        }
        Box(
            Modifier.size(58.dp).background(Brand.DeepBlue, CircleShape).border(1.dp, Brand.Blue.copy(alpha = 0.5f), CircleShape),
            contentAlignment = Alignment.Center,
        ) { HomoraLogo(Modifier.size(38.dp)) }
    }
}

private val ORBIT = listOf(Icons.Outlined.Lightbulb, Icons.Outlined.Videocam, Icons.Outlined.Speaker, Icons.Outlined.Thermostat, Icons.Outlined.Router)

/** Page 2: a shield that ticks itself, with smart-home devices orbiting it. */
@Composable
fun ShieldIllustration(active: Boolean, modifier: Modifier = Modifier) {
    val check = remember { Animatable(0f) }
    LaunchedEffect(active) {
        if (active) {
            check.snapTo(0f)
            check.animateTo(1f, tween(800, delayMillis = 250, easing = FastOutSlowInEasing))
        }
    }
    val t = rememberInfiniteTransition(label = "shield")
    val orbit by t.animateFloat(0f, 360f, infiniteRepeatable(tween(16000, easing = LinearEasing)), label = "orbit")
    val pulse by t.animateFloat(0f, 1f, infiniteRepeatable(tween(2200, easing = LinearEasing)), label = "pulse")
    val good = LocalStatusColors.current.good

    Box(modifier.size(ArtSize), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f
            drawCircle(Faint, r - 24.dp.toPx(), center, style = Stroke(1.5f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 12f))))
            // Expanding ripple from the shield.
            drawCircle(Brand.Blue.copy(alpha = 0.35f * (1f - pulse)), 50.dp.toPx() + pulse * 60.dp.toPx(), center, style = Stroke(2f))

            // Shield in a 100-unit box, 130dp tall.
            val s = 130.dp.toPx() / 100f
            val ox = center.x - 50f * s
            val oy = center.y - 52f * s
            fun p(x: Float, y: Float) = Offset(ox + x * s, oy + y * s)
            val shield = Path().apply {
                moveTo(p(50f, 6f).x, p(50f, 6f).y)
                lineTo(p(88f, 20f).x, p(88f, 20f).y)
                lineTo(p(88f, 48f).x, p(88f, 48f).y)
                cubicTo(p(88f, 74f).x, p(88f, 74f).y, p(70f, 90f).x, p(70f, 90f).y, p(50f, 98f).x, p(50f, 98f).y)
                cubicTo(p(30f, 90f).x, p(30f, 90f).y, p(12f, 74f).x, p(12f, 74f).y, p(12f, 48f).x, p(12f, 48f).y)
                lineTo(p(12f, 20f).x, p(12f, 20f).y)
                close()
            }
            drawPath(shield, Brush.verticalGradient(listOf(Brand.Blue.copy(alpha = 0.22f), Color.Transparent), oy, oy + 100f * s))
            drawPath(shield, Line, style = Stroke(3.dp.toPx(), join = StrokeJoin.Round))

            // Check mark drawn in two strokes.
            val a = p(33f, 52f); val b = p(46f, 65f); val e = p(69f, 40f)
            val k = check.value
            val first = (k / 0.4f).coerceIn(0f, 1f)
            val second = ((k - 0.4f) / 0.6f).coerceIn(0f, 1f)
            val w = 5.dp.toPx()
            if (first > 0f) drawLine(good, a, Offset(a.x + (b.x - a.x) * first, a.y + (b.y - a.y) * first), w, StrokeCap.Round)
            if (second > 0f) drawLine(good, b, Offset(b.x + (e.x - b.x) * second, b.y + (e.y - b.y) * second), w, StrokeCap.Round)
        }
        val radius = ArtSize.value / 2 - 24
        ORBIT.forEachIndexed { i, icon ->
            val ang = Math.toRadians((orbit + i * 360f / ORBIT.size).toDouble())
            Bubble(icon, Modifier.offset((cos(ang) * radius).toFloat().dp, (sin(ang) * radius).toFloat().dp), size = 46.dp)
        }
    }
}

/** Page 3: Wi-Fi waves rippling out, with saved rooms floating by. */
@Composable
fun SignalIllustration(modifier: Modifier = Modifier) {
    val t = rememberInfiniteTransition(label = "signal")
    val wave by t.animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "wave")
    val bob by t.animateFloat(-6f, 6f, infiniteRepeatable(tween(2400, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "bob")
    val status = LocalStatusColors.current

    Box(modifier.size(ArtSize), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val base = Offset(center.x, center.y + 46.dp.toPx())
            // Rings rippling out from the router.
            repeat(3) { i ->
                val f = (wave + i / 3f) % 1f
                drawCircle(Color.White.copy(alpha = 0.16f * (1f - f)), 20.dp.toPx() + f * 120.dp.toPx(), base, style = Stroke(1.5f))
            }
            // Three arcs lighting up in turn, like a signal going out.
            listOf(34.dp, 62.dp, 90.dp).forEachIndexed { i, rr ->
                val r = rr.toPx()
                val lit = ((wave * 3f - i).let { if (it < 0f) 0f else if (it > 1f) 2f - it else it }).coerceIn(0f, 1f)
                val color = lerpColor(Color.White.copy(alpha = 0.35f), Brand.Cyan, lit)
                drawArc(
                    color, -90f - 40f, 80f, false,
                    Offset(base.x - r, base.y - r), Size(r * 2, r * 2),
                    style = Stroke(9.dp.toPx(), cap = StrokeCap.Round),
                )
            }
            drawCircle(Brand.Blue, 10.dp.toPx(), base)
        }
        RoomChip("Living room", "−48 dBm", status.good, Modifier.align(Alignment.TopStart).padding(top = 18.dp).offset(y = bob.dp))
        RoomChip("Kitchen", "−71 dBm", status.medium, Modifier.align(Alignment.BottomEnd).padding(bottom = 24.dp).offset(y = (-bob).dp))
    }
}

@Composable
private fun RoomChip(name: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Row(
        modifier
            .background(Color(0xFF12161C), RoundedCornerShape(50))
            .border(1.dp, Color.White.copy(alpha = 0.14f), RoundedCornerShape(50))
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).background(color, CircleShape))
        Spacer(Modifier.width(8.dp))
        Text(name, style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.width(8.dp))
        Text(value, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Page 4: a phone keeping its data inside a locked ring. */
@Composable
fun PrivacyIllustration(modifier: Modifier = Modifier) {
    val t = rememberInfiniteTransition(label = "privacy")
    val spin by t.animateFloat(0f, 360f, infiniteRepeatable(tween(14000, easing = LinearEasing)), label = "spin")
    val breathe by t.animateFloat(0.92f, 1.06f, infiniteRepeatable(tween(1600, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "breathe")

    Box(modifier.size(ArtSize), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val r = size.minDimension / 2f - 20.dp.toPx()
            rotate(spin, center) {
                drawCircle(Brand.Blue.copy(alpha = 0.55f), r, center, style = Stroke(2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(4f, 22f)), cap = StrokeCap.Round))
            }
            drawCircle(Faint, r - 26.dp.toPx(), center, style = Stroke(1.5f))
            // Phone outline.
            val pw = 104.dp.toPx(); val ph = 176.dp.toPx()
            val tl = Offset(center.x - pw / 2, center.y - ph / 2)
            drawRoundRect(Color(0xFF0E1116), tl, Size(pw, ph), CornerRadius(22.dp.toPx()))
            drawRoundRect(Line, tl, Size(pw, ph), CornerRadius(22.dp.toPx()), style = Stroke(3.dp.toPx()))
            drawLine(Line.copy(alpha = 0.5f), Offset(center.x - 14.dp.toPx(), tl.y + 12.dp.toPx()), Offset(center.x + 14.dp.toPx(), tl.y + 12.dp.toPx()), 3.dp.toPx(), StrokeCap.Round)
            // Device list lines on the screen.
            repeat(3) { i ->
                val y = center.y + 30.dp.toPx() + i * 16.dp.toPx()
                drawLine(Line.copy(alpha = 0.25f), Offset(tl.x + 20.dp.toPx(), y), Offset(tl.x + pw - (if (i == 1) 40 else 24).dp.toPx(), y), 4.dp.toPx(), StrokeCap.Round)
            }
        }
        Box(
            Modifier
                .offset(y = (-24).dp)
                .graphicsLayer { scaleX = breathe; scaleY = breathe }
                .size(58.dp)
                .background(Brush.verticalGradient(listOf(Brand.Cyan, Brand.Blue)), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.Lock, null, Modifier.size(28.dp), tint = Color.White)
        }
    }
}

private fun lerpColor(a: Color, b: Color, f: Float) = Color(
    red = a.red + (b.red - a.red) * f,
    green = a.green + (b.green - a.green) * f,
    blue = a.blue + (b.blue - a.blue) * f,
    alpha = a.alpha + (b.alpha - a.alpha) * f,
)
