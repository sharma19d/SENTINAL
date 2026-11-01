package com.charonsecurity.homora.ui.components

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
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

@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 8.dp),
    )
}

/** A flat card: no elevation, just a quiet surface. */
@Composable
fun PlainCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    val colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow)
    if (onClick != null) {
        Card(onClick = onClick, modifier = modifier.fillMaxWidth(), colors = colors) { content() }
    } else {
        Card(modifier = modifier.fillMaxWidth(), colors = colors) { content() }
    }
}

@Composable
fun EmptyState(icon: ImageVector, title: String, body: String, action: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, null, Modifier.size(48.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))
        Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        Spacer(Modifier.height(24.dp))
        action()
    }
}

/** Scan button, progress while running, and the reason when a scan can't run. */
@Composable
fun ScanControl(state: ScanState, lastScanAt: Long?, onScan: () -> Unit, onStop: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        when (state) {
            is ScanState.Running -> {
                val p = state.progress
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        if (p.phase == Scanner.Phase.CHECKING_DEVICES) pluralStringResource(R.plurals.scan_phase_checking, p.devicesFound, p.devicesFound)
                        else pluralStringResource(R.plurals.scan_phase_discovering, p.devicesFound, p.devicesFound),
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedButton(onClick = onStop) { Text(stringResource(R.string.scan_stop)) }
                }
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(progress = { p.fraction }, modifier = Modifier.fillMaxWidth())
            }
            else -> {
                if (state is ScanState.Failed) {
                    Text(
                        stringResource(
                            when (state.reason) {
                                Telemetry.ScanFailure.NO_WIFI -> R.string.err_no_wifi
                                Telemetry.ScanFailure.NOT_PRIVATE_NETWORK -> R.string.err_not_private
                                Telemetry.ScanFailure.ERROR -> R.string.err_scan
                            },
                        ),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(onClick = onScan) { Text(stringResource(if (lastScanAt == null) R.string.action_scan else R.string.action_rescan)) }
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
    androidx.compose.foundation.Canvas(modifier.size(10.dp)) { drawCircle(color) }
}

@Composable
fun NumberedSteps(steps: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        steps.forEachIndexed { i, s ->
            Row {
                Text("${i + 1}.", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(24.dp))
                Text(s, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
