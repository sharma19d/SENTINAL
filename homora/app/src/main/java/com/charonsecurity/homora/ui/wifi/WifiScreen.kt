package com.charonsecurity.homora.ui.wifi

import android.media.AudioManager
import android.media.ToneGenerator
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.data.RoomReading
import com.charonsecurity.homora.net.Probe
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.EmptyState
import com.charonsecurity.homora.ui.components.PlainCard
import com.charonsecurity.homora.ui.components.SectionHeader
import com.charonsecurity.homora.ui.components.hasWifiDetailPermission
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.components.roomAdvice
import com.charonsecurity.homora.ui.components.wifiDetailPermissions
import com.charonsecurity.homora.wifi.Connection
import com.charonsecurity.homora.wifi.SignalZone
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun WifiScreen(container: AppContainer, onSmartHelper: () -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val haptics = LocalHapticFeedback.current
    val app by container.store.state.collectAsStateWithLifecycle()
    val sound by container.prefs.meterSound.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()

    var conn by remember { mutableStateOf<Connection?>(null) }
    var connected by remember { mutableStateOf(true) }
    val samples = remember { mutableStateListOf<Int>() }
    val latencies = remember { mutableStateListOf<Double>() }
    var latency by remember { mutableStateOf<Double?>(null) }
    var naming by remember { mutableStateOf(false) }
    var permission by remember { mutableStateOf(hasWifiDetailPermission(context)) }
    var spotsSaved by remember { mutableIntStateOf(0) }
    var soundUsed by remember { mutableStateOf(false) }
    val askPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        permission = hasWifiDetailPermission(context)
        Telemetry.permissionResult(permission)
    }

    val smoothed = samples.takeLast(3).takeIf { it.isNotEmpty() }?.average()
    val trend = if (samples.size >= 6) {
        val d = samples.takeLast(3).average() - samples.takeLast(6).take(3).average()
        if (d > 2) 1 else if (d < -2) -1 else 0
    } else 0

    // Polling runs only while the screen is visible; it stops in the background.
    // Keyed on [sound] so turning the beeper on or off takes effect at once.
    LaunchedEffect(sound) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            coroutineScope {
                launch {
                    var lastZone: SignalZone? = null
                    while (isActive) {
                        val c = withContext(Dispatchers.IO) { container.wifi.connection() }
                        connected = c != null
                        conn = c
                        if (c != null) {
                            samples += c.rssi
                            if (samples.size > MAX_SAMPLES) samples.removeAt(0)
                            val zone = SignalZone.of(c.rssi)
                            if (zone == SignalZone.DEAD && lastZone != null && lastZone != SignalZone.DEAD) {
                                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                            }
                            lastZone = zone
                        }
                        delay(1000)
                    }
                }
                launch {
                    val gateway = withContext(Dispatchers.IO) { container.wifi.lanInfo()?.gateway } ?: return@launch
                    val tcpPort = withContext(Dispatchers.IO) {
                        if (Probe.dnsRoundTripMs(gateway) != null) null
                        else listOf(80, 443, 53).firstOrNull { Probe.tcpRoundTripMs(gateway, it) != null }
                    }
                    while (isActive) {
                        val ms = withContext(Dispatchers.IO) {
                            if (tcpPort == null) Probe.dnsRoundTripMs(gateway) else Probe.tcpRoundTripMs(gateway, tcpPort)
                        }
                        if (ms != null) {
                            latencies += ms
                            if (latencies.size > 20) latencies.removeAt(0)
                        }
                        latency = latencies.takeLast(5).sorted().getOrNull(latencies.takeLast(5).size / 2)
                        delay(500)
                    }
                }
                if (sound) {
                    launch { beep { samples.lastOrNull() } }
                }
            }
        }
    }

    val started = remember { System.currentTimeMillis() }
    DisposableEffect(Unit) {
        onDispose { Telemetry.meterSession(System.currentTimeMillis() - started, spotsSaved, soundUsed) }
    }

    WifiContent(
        connected = connected,
        conn = conn,
        rssi = smoothed,
        trend = trend,
        latencyMs = latency,
        samples = samples.toList(),
        sound = sound,
        hasPermission = permission,
        rooms = app.rooms,
        onSaveSpot = { naming = true },
        onSound = {
            container.prefs.setMeterSound(it)
            if (it) soundUsed = true
        },
        onAllow = { askPermission.launch(wifiDetailPermissions()) },
        onDeleteRoom = { name -> scope.launch { container.store.deleteRoom(name) } },
        onSmartHelper = { Telemetry.smartHelperOpened(); onSmartHelper() },
    )

    if (naming) {
        var name by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { naming = false },
            title = { Text(stringResource(R.string.wifi_save_spot)) },
            text = {
                OutlinedTextField(name, { name = it.take(40) }, singleLine = true, placeholder = { Text(stringResource(R.string.wifi_spot_name_hint)) })
            },
            confirmButton = {
                TextButton(enabled = name.isNotBlank(), onClick = {
                    val recent = samples.takeLast(10)
                    val reading = RoomReading(
                        name = name.trim(),
                        rssi = recent.average().toInt(),
                        latencyMs = latencies.takeLast(10).sorted().let { it.getOrNull(it.size / 2) },
                        band = conn?.band?.label,
                        at = System.currentTimeMillis(),
                    )
                    scope.launch { container.store.addRoom(reading) }
                    spotsSaved++
                    naming = false
                }) { Text(stringResource(R.string.save)) }
            },
            dismissButton = { TextButton(onClick = { naming = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

/** The meter screen's layout, stateless so it can be previewed and snapshot-tested. */
@Composable
fun WifiContent(
    connected: Boolean,
    conn: Connection?,
    rssi: Double?,
    trend: Int,
    latencyMs: Double?,
    samples: List<Int>,
    sound: Boolean,
    hasPermission: Boolean,
    rooms: List<RoomReading>,
    onSaveSpot: () -> Unit,
    onSound: (Boolean) -> Unit,
    onAllow: () -> Unit,
    onDeleteRoom: (String) -> Unit,
    onSmartHelper: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        if (!connected) {
            EmptyState(Icons.Outlined.WifiOff, stringResource(R.string.nav_wifi), stringResource(R.string.wifi_not_connected)) {}
            return@Column
        }
        Column(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(conn?.ssid ?: stringResource(R.string.wifi_your_network), style = MaterialTheme.typography.titleMedium)
            SignalGauge(rssi, trend)
            val c = conn
            Text(
                listOfNotNull(
                    latencyMs?.let { stringResource(R.string.wifi_router_latency, "%.0f".format(it)) } ?: stringResource(R.string.wifi_router_latency_none),
                    c?.band?.label,
                    c?.linkMbps?.takeIf { it > 0 }?.let { stringResource(R.string.wifi_link_rate, it) },
                ).joinToString("  ·  "),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(stringResource(R.string.wifi_link_rate_hint), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
        Sparkline(samples, Modifier.padding(horizontal = 24.dp, vertical = 16.dp))

        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = onSaveSpot, enabled = samples.size >= 3) { Text(stringResource(R.string.wifi_save_spot)) }
            Spacer(Modifier.weight(1f))
            Text(stringResource(R.string.wifi_sound), style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.width(8.dp))
            Switch(checked = sound, onCheckedChange = onSound)
        }
        if (sound) {
            Text(
                stringResource(R.string.wifi_sound_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }

        if (!hasPermission) {
            PlainCard(Modifier.padding(16.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Text(stringResource(R.string.wifi_permission_needed), style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = onAllow) { Text(stringResource(R.string.wifi_allow)) }
                }
            }
        }

        SectionHeader(stringResource(R.string.wifi_rooms_title))
        if (rooms.isEmpty()) {
            Text(
                stringResource(R.string.wifi_rooms_empty),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        } else {
            rooms.sortedByDescending { it.rssi }.forEach { r -> RoomRow(r) { onDeleteRoom(r.name) } }
        }

        PlainCard(Modifier.padding(16.dp), onClick = onSmartHelper) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.smart_title), style = MaterialTheme.typography.titleSmall)
                    Text(stringResource(R.string.smart_subtitle), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null)
            }
        }
    }
}

@Composable
private fun RoomRow(r: RoomReading, onDelete: () -> Unit) {
    val zone = SignalZone.of(r.rssi)
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(r.name, style = MaterialTheme.typography.bodyLarge)
            Text(
                stringResource(zone.label()) + " · " + stringResource(R.string.wifi_dbm, r.rssi) + (r.band?.let { " · $it" } ?: ""),
                style = MaterialTheme.typography.bodySmall,
                color = zoneColor(zone),
            )
            Text(stringResource(zone.roomAdvice()), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        TextButton(onClick = onDelete) { Text(stringResource(R.string.wifi_room_delete)) }
    }
}

/** Geiger-counter style: the stronger the signal, the faster the beeps. */
private suspend fun beep(latest: () -> Int?) {
    val tone = try {
        ToneGenerator(AudioManager.STREAM_MUSIC, 45)
    } catch (_: RuntimeException) {
        return
    }
    try {
        while (true) {
            val rssi = latest()
            if (rssi != null) {
                tone.startTone(ToneGenerator.TONE_PROP_BEEP, 40)
                val f = SignalZone.fraction(rssi.toDouble())
                delay((1200 - 1050 * f).toLong())
            } else {
                delay(500)
            }
        }
    } finally {
        tone.release()
    }
}
