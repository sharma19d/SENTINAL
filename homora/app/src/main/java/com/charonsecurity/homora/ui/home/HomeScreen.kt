package com.charonsecurity.homora.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.outlined.FiberNew
import androidx.compose.material3.TextButton
import com.charonsecurity.homora.data.blockedStillPresent
import com.charonsecurity.homora.ui.components.ExpandableCard
import com.charonsecurity.homora.ui.devices.deviceName
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.GppBad
import androidx.compose.material.icons.outlined.GppMaybe
import androidx.compose.material.icons.outlined.PersonOff
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Radar
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.FindingType
import com.charonsecurity.homora.checks.Health
import com.charonsecurity.homora.checks.Severity
import com.charonsecurity.homora.data.HistoryKind
import com.charonsecurity.homora.data.ScanState
import com.charonsecurity.homora.ui.components.GlassCard
import com.charonsecurity.homora.ui.components.GlowButton
import com.charonsecurity.homora.ui.components.GlowGauge
import com.charonsecurity.homora.ui.components.HomoraLogo
import com.charonsecurity.homora.ui.components.SectionHeader
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.StatusPill
import com.charonsecurity.homora.ui.components.relativeTime
import com.charonsecurity.homora.ui.components.scanFailureText
import com.charonsecurity.homora.ui.components.scanPhaseText
import com.charonsecurity.homora.ui.components.text
import com.charonsecurity.homora.ui.devices.DeviceFilter
import com.charonsecurity.homora.ui.devices.isMarked
import com.charonsecurity.homora.ui.theme.LocalStatusColors
import com.charonsecurity.homora.wifi.Connection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun HomeScreen(
    container: AppContainer,
    onSettings: () -> Unit,
    onDevices: (DeviceFilter) -> Unit,
    onSecurity: () -> Unit,
    onWifi: () -> Unit,
    onLockout: () -> Unit,
    onDevice: (String) -> Unit = {},
    onFinding: (String) -> Unit = {},
) {
    val alerts by container.prefs.newDeviceAlerts.collectAsStateWithLifecycle()
    val scanState by container.scans.state.collectAsStateWithLifecycle()
    val app by container.store.state.collectAsStateWithLifecycle()
    val status = LocalStatusColors.current
    val scan = app.lastScan
    val running = scanState as? ScanState.Running

    val unmarked = remember(scan, app.known) { scan?.devices?.count { !isMarked(it, app) } ?: 0 }
    val score = remember(scan, unmarked) { scan?.let { Health.score(it.findings, unmarked) } }
    val level = score?.let(Health::level)

    // Read the Wi-Fi link once each time the screen becomes visible (and after a scan); no polling.
    var conn by remember { mutableStateOf<Connection?>(null) }
    var wifiKnown by remember { mutableStateOf(false) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(running == null) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            conn = withContext(Dispatchers.IO) { runCatching { container.wifi.connection() }.getOrNull() }
            wifiKnown = true
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            HomoraLogo(Modifier.size(46.dp))
            Spacer(Modifier.width(12.dp))
            Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
            IconButton(onClick = onSettings) { Icon(Icons.Outlined.Settings, stringResource(R.string.settings)) }
        }

        // Gauge: scan progress while scanning, otherwise the health score.
        val gaugeColor = when {
            running != null -> Color.White
            level == Health.Level.AT_RISK -> status.high
            level == Health.Level.FAIR -> status.medium
            else -> Color.White
        }
        Box(Modifier.fillMaxWidth().padding(top = 8.dp), contentAlignment = Alignment.Center) {
            GlowGauge(
                fraction = running?.progress?.fraction ?: (score ?: 0) / 100f,
                value = when {
                    running != null -> "${(running.progress.fraction * 100).toInt()}%"
                    score != null -> score.toString()
                    else -> "–"
                },
                caption = stringResource(if (running != null) R.string.home_scanning else R.string.home_health),
                color = gaugeColor,
            )
        }
        Box(Modifier.fillMaxWidth().offset(y = (-14).dp), contentAlignment = Alignment.Center) {
            when {
                running != null -> StatusPill(scanPhaseText(running.progress), Icons.Outlined.Radar, Color.White)
                level == Health.Level.SECURE -> StatusPill(stringResource(R.string.home_level_secure), Icons.Outlined.VerifiedUser, status.good)
                level == Health.Level.FAIR -> StatusPill(stringResource(R.string.home_level_fair), Icons.Outlined.GppMaybe, status.medium)
                level == Health.Level.AT_RISK -> StatusPill(stringResource(R.string.home_level_risk), Icons.Outlined.GppBad, status.high)
                else -> StatusPill(stringResource(R.string.home_not_scanned), Icons.Outlined.Shield, MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }

        Spacer(Modifier.height(6.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatTile(
                Icons.Outlined.Devices,
                scan?.devices?.size?.toString() ?: "–",
                stringResource(R.string.nav_devices),
                Modifier.weight(1f),
            ) { onDevices(DeviceFilter.ALL) }
            StatTile(
                Icons.Outlined.Shield,
                scan?.findings?.size?.toString() ?: "–",
                stringResource(R.string.home_issues),
                Modifier.weight(1f),
                onClick = onSecurity,
            )
            StatTile(
                if (wifiKnown && conn == null) Icons.Outlined.WifiOff else Icons.Outlined.Wifi,
                conn?.ssid ?: if (wifiKnown && conn == null) stringResource(R.string.home_wifi_off) else stringResource(R.string.nav_wifi),
                stringResource(if (wifiKnown && conn == null) R.string.home_wifi_disconnected else R.string.home_wifi_connected),
                Modifier.weight(1f),
                onClick = onWifi,
            )
        }

        Spacer(Modifier.height(22.dp))
        if (running != null) {
            GlowButton(stringResource(R.string.home_stop_scan), container.scans::cancel, icon = Icons.Outlined.Stop)
        } else {
            GlowButton(stringResource(R.string.home_scan_network), container.scans::start, icon = Icons.Outlined.PlayArrow)
        }
        AnimatedVisibility(scanState is ScanState.Failed, enter = fadeIn(), exit = fadeOut()) {
            (scanState as? ScanState.Failed)?.let {
                Text(
                    scanFailureText(it.reason),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                )
            }
        }
        if (scan != null && running == null) {
            Text(
                stringResource(R.string.last_scan, relativeTime(scan.at)),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            )
        }

        Spacer(Modifier.height(16.dp))
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (scan != null) {
                // Blocked devices that are still here come first: that's the one thing to act on now.
                val stillHere = remember(app) { app.blockedStillPresent() }
                if (stillHere.isNotEmpty()) {
                    InsightRow(
                        pluralStringResource(R.plurals.home_blocked_present, stillHere.size, stillHere.size),
                        dot = status.high,
                        onClick = { onDevice(stillHere.first().identityKey) },
                    )
                }

                val n = scan.findings.size
                if (n > 0) {
                    val worst = scan.findings.minOf { it.type.severity.ordinal }
                    ExpandableCard(
                        pluralStringResource(R.plurals.home_risks, n, n),
                        icon = Icons.Outlined.GppMaybe,
                        iconTint = if (worst == Severity.HIGH.ordinal) status.high else status.medium,
                    ) {
                        Column {
                            scan.findings.take(4).forEach { f ->
                                MiniRow(
                                    stringResource(f.type.text().title),
                                    f.deviceName ?: f.deviceIp,
                                    if (f.type.severity == Severity.HIGH) status.high else if (f.type.severity == Severity.MEDIUM) status.medium else MaterialTheme.colorScheme.outline,
                                ) { onFinding(f.id) }
                            }
                            TextButton(onClick = onSecurity, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.home_see_all)) }
                        }
                    }
                } else {
                    InsightRow(stringResource(R.string.home_no_risks), icon = Icons.Outlined.CheckCircle, iconTint = status.good, onClick = onSecurity)
                }

                val fresh = remember(scan, app.known) { scan.devices.filter { it.identityKey in scan.newKeys && !isMarked(it, app) } }
                if (fresh.isNotEmpty()) {
                    ExpandableCard(
                        pluralStringResource(R.plurals.home_new_devices, fresh.size, fresh.size),
                        icon = Icons.Outlined.FiberNew,
                    ) {
                        Column {
                            fresh.take(5).forEach { d ->
                                MiniRow(deviceName(d, app), d.ip, Color.White) { onDevice(d.identityKey) }
                            }
                            if (!alerts) {
                                TextButton(onClick = onSettings, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.home_alerts_cta)) }
                            }
                        }
                    }
                }

                if (unmarked > 0) {
                    InsightRow(pluralStringResource(R.plurals.home_unmarked, unmarked, unmarked), dot = Color.White, onClick = { onDevices(DeviceFilter.UNKNOWN) })
                }
            }
            InsightRow(stringResource(R.string.lockout_link), icon = Icons.Outlined.PersonOff, onClick = onLockout)
        }

        if (app.history.isNotEmpty()) {
            SectionHeader(stringResource(R.string.history_title), inset = 4.dp)
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(vertical = 6.dp)) {
                    app.history.take(5).forEach { e ->
                        val subject = FindingType.entries.firstOrNull { it.name == e.subject }?.let { stringResource(it.text().title) } ?: e.subject
                        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                            StatusDot(
                                when (e.kind) {
                                    HistoryKind.NEW_DEVICE -> Color.White
                                    HistoryKind.ISSUE_FOUND -> status.medium
                                    HistoryKind.ISSUE_FIXED -> status.good
                                },
                            )
                            Spacer(Modifier.width(12.dp))
                            Text(
                                when (e.kind) {
                                    HistoryKind.NEW_DEVICE -> stringResource(R.string.history_new_device, subject)
                                    HistoryKind.ISSUE_FOUND -> stringResource(R.string.history_issue_found, subject)
                                    HistoryKind.ISSUE_FIXED -> stringResource(R.string.history_issue_fixed, subject)
                                },
                                style = MaterialTheme.typography.bodyMedium,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(relativeTime(e.at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(28.dp))
    }
}

/** A compact tappable line inside an expanded card. */
@Composable
private fun MiniRow(title: String, sub: String?, dot: Color, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable(onClick = onClick).padding(vertical = 10.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StatusDot(dot)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            sub?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1) }
        }
        Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun StatTile(icon: ImageVector, value: String, label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    GlassCard(modifier.height(118.dp), onClick = onClick) {
        Column(
            Modifier.fillMaxSize().padding(horizontal = 8.dp, vertical = 14.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Icon(icon, null, Modifier.size(26.dp), tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
            Text(value, style = MaterialTheme.typography.titleLarge, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun InsightRow(text: String, onClick: () -> Unit, dot: Color? = null, icon: ImageVector? = null, iconTint: Color = MaterialTheme.colorScheme.onSurface) {
    GlassCard(Modifier.fillMaxWidth(), onClick = onClick) {
        Row(Modifier.padding(horizontal = 18.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            when {
                dot != null -> StatusDot(dot, Modifier.size(12.dp))
                icon != null -> Icon(icon, null, Modifier.size(20.dp), tint = iconTint)
            }
            Spacer(Modifier.width(14.dp))
            Text(text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
