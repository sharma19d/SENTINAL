package com.charonsecurity.homora.ui.wifi

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.R
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.theme.LocalStatusColors
import com.charonsecurity.homora.wifi.SignalZone

@Composable
fun zoneColor(zone: SignalZone): Color {
    val s = LocalStatusColors.current
    return when (zone) {
        SignalZone.EXCELLENT, SignalZone.GOOD, SignalZone.FAIR -> MaterialTheme.colorScheme.primary
        SignalZone.WEAK -> s.medium
        SignalZone.DEAD -> s.high
    }
}

/**
 * Arc gauge for signal strength. Android refreshes the signal only every
 * second or so, so the needle glides between readings instead of jumping.
 */
@Composable
fun SignalGauge(rssi: Double?, trend: Int, modifier: Modifier = Modifier) {
    val fraction by animateFloatAsState(rssi?.let { SignalZone.fraction(it) } ?: 0f, tween(900), label = "gauge")
    val zone = rssi?.let { SignalZone.of(it.toInt()) }
    val color = zone?.let { zoneColor(it) } ?: MaterialTheme.colorScheme.outline
    val track = Color.White.copy(alpha = 0.08f)
    Box(modifier.padding(top = 12.dp).size(240.dp, 200.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(200.dp)) {
            val stroke = 14.dp.toPx()
            val inset = stroke
            val arcSize = Size(size.width - stroke, size.height - stroke)
            drawArc(track, 150f, 240f, false, Offset(inset, inset), arcSize, style = Stroke(stroke, cap = StrokeCap.Round))
            if (fraction > 0f) {
                val sweep = 240f * fraction
                drawArc(color.copy(alpha = 0.12f), 150f, sweep, false, Offset(inset, inset), arcSize, style = Stroke(stroke * 2f, cap = StrokeCap.Round))
                drawArc(color, 150f, sweep, false, Offset(inset, inset), arcSize, style = Stroke(stroke, cap = StrokeCap.Round))
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(zone?.let { stringResource(it.label()) } ?: "–", style = MaterialTheme.typography.headlineMedium, color = color)
            if (rssi != null) {
                Text(stringResource(R.string.wifi_dbm, rssi.toInt()), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(
                        when {
                            trend > 0 -> R.string.wifi_trend_up
                            trend < 0 -> R.string.wifi_trend_down
                            else -> R.string.wifi_trend_steady
                        },
                    ),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** The last minute of signal readings. */
@Composable
fun Sparkline(samples: List<Int>, modifier: Modifier = Modifier) {
    val line = MaterialTheme.colorScheme.primary
    val grid = MaterialTheme.colorScheme.outlineVariant
    Canvas(modifier.fillMaxWidth().height(56.dp)) {
        drawLine(grid, Offset(0f, size.height), Offset(size.width, size.height), 1f)
        if (samples.size < 2) return@Canvas
        val step = size.width / (MAX_SAMPLES - 1)
        val x0 = size.width - step * (samples.size - 1)
        val path = Path()
        samples.forEachIndexed { i, v ->
            val y = size.height * (1f - SignalZone.fraction(v.toDouble()))
            val x = x0 + i * step
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, line, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
    }
}

const val MAX_SAMPLES = 60
