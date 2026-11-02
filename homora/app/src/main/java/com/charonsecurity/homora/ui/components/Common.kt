package com.charonsecurity.homora.ui.components

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.charonsecurity.homora.R
import com.charonsecurity.homora.data.ScanState
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry

/** Permissions that unlock the Wi-Fi name and nearby-network list. */
fun wifiDetailPermissions(): Array<String> = buildList {
    add(Manifest.permission.ACCESS_FINE_LOCATION)
    add(Manifest.permission.ACCESS_COARSE_LOCATION)
    if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.NEARBY_WIFI_DEVICES)
}.toTypedArray()

fun hasWifiDetailPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

private val CardShape = RoundedCornerShape(20.dp)

/** The big title at the top of each tab, with optional actions on the right. */
@Composable
fun TabHeader(title: String, modifier: Modifier = Modifier, actions: @Composable RowScope.() -> Unit = {}) {
    Row(
        modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 12.dp, bottom = 8.dp).height(56.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
        actions()
    }
}

@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier, inset: Dp = 20.dp) {
    Text(
        text.uppercase(),
        style = MaterialTheme.typography.labelMedium.copy(letterSpacing = 1.2.sp),
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.padding(start = inset, end = inset, top = 24.dp, bottom = 10.dp),
    )
}

/**
 * Frosted-glass card: a dark surface with a faint top highlight and a hairline
 * border, as in the design. Clickable when [onClick] is set.
 */
@Composable
fun GlassCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, shape: Shape = CardShape, content: @Composable () -> Unit) {
    val c = MaterialTheme.colorScheme
    val border = BorderStroke(1.dp, Brush.verticalGradient(listOf(Color.White.copy(alpha = 0.10f), Color.White.copy(alpha = 0.03f))))
    val bg = Brush.verticalGradient(listOf(c.surfaceContainerHigh, c.surfaceContainerLow))
    if (onClick != null) {
        Surface(onClick = onClick, modifier = modifier, shape = shape, color = Color.Transparent, border = border) {
            Box(Modifier.background(bg)) { content() }
        }
    } else {
        Surface(modifier = modifier, shape = shape, color = Color.Transparent, border = border) {
            Box(Modifier.background(bg)) { content() }
        }
    }
}

/** Kept for existing screens: a full-width glass card. */
@Composable
fun PlainCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    GlassCard(modifier.fillMaxWidth(), onClick, content = content)
}

/** A rounded square holding an icon, used for device types and services. */
@Composable
fun IconTile(icon: ImageVector, modifier: Modifier = Modifier, size: Dp = 48.dp, tint: Color = MaterialTheme.colorScheme.onSurface) {
    Box(
        modifier
            .size(size)
            .background(Brush.verticalGradient(listOf(Color.White.copy(alpha = 0.09f), Color.White.copy(alpha = 0.03f))), RoundedCornerShape(size * 0.3f))
            .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(size * 0.3f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, Modifier.size(size * 0.5f), tint = tint)
    }
}

/** The glowing white pill from the design, for the one main action on a screen. */
@Composable
fun GlowButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null, enabled: Boolean = true) {
    val shape = RoundedCornerShape(50)
    Surface(
        onClick = onClick,
        enabled = enabled,
        shape = shape,
        color = Color.Transparent,
        modifier = modifier
            .fillMaxWidth()
            .height(58.dp)
            .shadow(if (enabled) 22.dp else 0.dp, shape, ambientColor = Color.White, spotColor = Color.White),
    ) {
        Row(
            Modifier
                .background(Brush.verticalGradient(listOf(Color(0xFFFFFFFF), Color(0xFFC9CED6))))
                .padding(horizontal = 24.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (icon != null) {
                Icon(icon, null, Modifier.size(22.dp), tint = Color(0xFF0A0D12))
                Spacer(Modifier.width(10.dp))
            }
            Text(text, color = Color(0xFF0A0D12), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** A selectable pill (filter chips in the design). */
@Composable
fun PillChip(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val c = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(50),
        color = if (selected) c.primary else Color.Transparent,
        contentColor = if (selected) c.onPrimary else c.onSurfaceVariant,
        border = if (selected) null else BorderStroke(1.dp, Color.White.copy(alpha = 0.14f)),
        modifier = modifier.height(40.dp),
    ) {
        Box(Modifier.padding(horizontal = 18.dp), contentAlignment = Alignment.Center) {
            Text(text, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** A small rounded badge with an icon, like "Secure" under the gauge. */
@Composable
fun StatusPill(text: String, icon: ImageVector, color: Color, modifier: Modifier = Modifier) {
    Row(
        modifier
            .background(Color.White.copy(alpha = 0.04f), RoundedCornerShape(50))
            .border(1.dp, Color.White.copy(alpha = 0.14f), RoundedCornerShape(50))
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, Modifier.size(18.dp), tint = color)
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurface)
    }
}

/**
 * The glowing arc gauge from the home screen. [fraction] fills the arc;
 * the value and caption sit in the middle. Fills smoothly on first show.
 */
@Composable
fun GlowGauge(fraction: Float, value: String, caption: String, modifier: Modifier = Modifier, color: Color = Color.White) {
    val start = remember { Animatable(0f) }
    LaunchedEffect(Unit) { start.animateTo(1f, tween(1100, easing = FastOutSlowInEasing)) }
    val target by animateFloatAsState(fraction.coerceIn(0f, 1f), tween(700, easing = FastOutSlowInEasing), label = "gauge")
    val shown = target * start.value
    val track = Color.White.copy(alpha = 0.08f)
    Box(modifier.size(260.dp, 230.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(230.dp)) {
            val stroke = 14.dp.toPx()
            val inset = stroke * 1.6f
            val arc = Size(size.width - inset * 2, size.height - inset * 2)
            val tl = Offset(inset, inset)
            drawArc(track, 135f, 270f, false, tl, arc, style = Stroke(stroke, cap = StrokeCap.Round))
            if (shown > 0.001f) {
                val sweep = 270f * shown
                // Soft glow: two wider, fainter passes under the solid arc.
                drawArc(color.copy(alpha = 0.10f), 135f, sweep, false, tl, arc, style = Stroke(stroke * 2.6f, cap = StrokeCap.Round))
                drawArc(color.copy(alpha = 0.22f), 135f, sweep, false, tl, arc, style = Stroke(stroke * 1.6f, cap = StrokeCap.Round))
                drawArc(color, 135f, sweep, false, tl, arc, style = Stroke(stroke, cap = StrokeCap.Round))
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, style = MaterialTheme.typography.displayLarge.copy(fontWeight = FontWeight.Bold, fontSize = 64.sp))
            Text(caption, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
        }
    }
}

@Composable
fun EmptyState(icon: ImageVector, title: String, body: String, action: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        IconTile(icon, size = 72.dp)
        Spacer(Modifier.height(20.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))
        Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        Spacer(Modifier.height(28.dp))
        action()
    }
}

@Composable
fun scanFailureText(reason: Telemetry.ScanFailure): String = stringResource(
    when (reason) {
        Telemetry.ScanFailure.NO_WIFI -> R.string.err_no_wifi
        Telemetry.ScanFailure.NOT_PRIVATE_NETWORK -> R.string.err_not_private
        Telemetry.ScanFailure.ERROR -> R.string.err_scan
    },
)

@Composable
fun scanPhaseText(p: Scanner.Progress): String =
    if (p.phase == Scanner.Phase.CHECKING_DEVICES) pluralStringResource(R.plurals.scan_phase_checking, p.devicesFound, p.devicesFound)
    else pluralStringResource(R.plurals.scan_phase_discovering, p.devicesFound, p.devicesFound)

/** Scan button, progress while running, and the reason when a scan can't run. */
@Composable
fun ScanControl(state: ScanState, lastScanAt: Long?, onScan: () -> Unit, onStop: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        when (state) {
            is ScanState.Running -> GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    val p = state.progress
                    val fraction by animateFloatAsState(p.fraction, tween(300), label = "scan")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(scanPhaseText(p), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        TextButton(onClick = onStop) { Text(stringResource(R.string.scan_stop)) }
                    }
                    Spacer(Modifier.height(8.dp))
                    LinearProgressIndicator(
                        progress = { fraction },
                        modifier = Modifier.fillMaxWidth().height(6.dp),
                        color = MaterialTheme.colorScheme.primary,
                        trackColor = Color.White.copy(alpha = 0.08f),
                        strokeCap = StrokeCap.Round,
                        gapSize = 0.dp,
                        drawStopIndicator = {},
                    )
                }
            }
            else -> {
                if (state is ScanState.Failed) {
                    Text(
                        scanFailureText(state.reason),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(bottom = 10.dp),
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Surface(
                        onClick = onScan,
                        shape = RoundedCornerShape(50),
                        color = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary,
                    ) {
                        Text(
                            stringResource(if (lastScanAt == null) R.string.action_scan else R.string.action_rescan),
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 11.dp),
                        )
                    }
                    if (lastScanAt != null) {
                        Text(
                            stringResource(R.string.last_scan, relativeTime(lastScanAt)),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun StatusDot(color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier.size(10.dp)) {
        drawCircle(color.copy(alpha = 0.25f), radius = size.minDimension / 2f)
        drawCircle(color, radius = size.minDimension / 3.2f)
    }
}

@Composable
fun NumberedSteps(steps: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        steps.forEachIndexed { i, s ->
            Row {
                Box(
                    Modifier.size(24.dp).background(Color.White.copy(alpha = 0.08f), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("${i + 1}", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.width(12.dp))
                Text(s, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 2.dp))
            }
        }
    }
}
