package com.charonsecurity.homora.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import com.charonsecurity.homora.ui.theme.Brand

/**
 * The Homora mark (an X guarding a Wi-Fi signal), drawn from the same
 * geometry as the launcher icon (tools/make_icon.py) so it can animate.
 *
 * [progress] runs 0→1: the four arms grow out from the centre, the dot pops
 * in, then the signal arcs sweep open one by one. 1 draws the finished mark.
 */
@Composable
fun HomoraLogo(modifier: Modifier = Modifier, progress: Float = 1f, armColor: Color = Color(0xFFEEF2FA)) {
    Canvas(modifier) { drawLogo(progress.coerceIn(0f, 1f), armColor) }
}

private val ARMS = listOf(
    floatArrayOf(46.71f, 50.31f, 32.66f, 39.45f),
    floatArrayOf(61.29f, 50.31f, 75.34f, 39.45f),
    floatArrayOf(47.17f, 62.12f, 33.63f, 74.37f),
    floatArrayOf(60.83f, 62.12f, 74.37f, 74.37f),
)

// Signal arcs share the dot's centre; (radius, half-angle in degrees).
private val ARCS = listOf(12.03f to 26f, 20.18f to 33f, 28.81f to 36f)
private const val CX = 54f
private const val CY = 55.94f

private fun seg(p: Float, start: Float, end: Float) = ((p - start) / (end - start)).coerceIn(0f, 1f)

private fun easeOut(t: Float) = 1f - (1f - t) * (1f - t) * (1f - t)

private fun DrawScope.drawLogo(p: Float, armColor: Color) {
    // The geometry lives in a 108-unit box; the mark spans x 29..79 and y 25..78.
    val viewSize = 54f
    val scale = minOf(size.width, size.height) / viewSize
    val ox = (size.width - viewSize * scale) / 2f
    val oy = (size.height - viewSize * scale) / 2f
    fun x(v: Float) = ox + (v - 27f) * scale
    fun y(v: Float) = oy + (v - 24.5f) * scale

    val armStroke = 6.79f * scale
    ARMS.forEachIndexed { i, a ->
        val t = easeOut(seg(p, 0.05f * i, 0.30f + 0.05f * i))
        if (t <= 0f) return@forEachIndexed
        val sx = x(a[0]); val sy = y(a[1])
        val ex = sx + (x(a[2]) - sx) * t
        val ey = sy + (y(a[3]) - sy) * t
        drawLine(armColor, Offset(sx, sy), Offset(ex, ey), armStroke, StrokeCap.Round)
    }

    val blue = Brush.linearGradient(listOf(Brand.Cyan, Brand.Blue), Offset(x(30f), y(26f)), Offset(x(78f), y(60f)))
    val dot = easeOut(seg(p, 0.30f, 0.48f))
    if (dot > 0f) {
        val r = 3.69f * scale * (if (dot < 1f) 0.6f + 0.6f * dot - 0.2f * dot * dot else 1f)
        drawCircle(blue, r, Offset(x(CX), y(CY)))
    }

    val arcStroke = 4.07f * scale
    ARCS.forEachIndexed { i, (radius, half) ->
        val t = easeOut(seg(p, 0.45f + 0.15f * i, 0.75f + 0.08f * i))
        if (t <= 0f) return@forEachIndexed
        val r = radius * scale
        val sweep = 2f * half * t
        drawArc(
            brush = blue,
            startAngle = -90f - sweep / 2f,
            sweepAngle = sweep,
            useCenter = false,
            topLeft = Offset(x(CX) - r, y(CY) - r),
            size = Size(r * 2, r * 2),
            style = Stroke(arcStroke, cap = StrokeCap.Round),
        )
    }
}
