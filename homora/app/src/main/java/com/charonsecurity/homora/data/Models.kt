package com.charonsecurity.homora.data

import com.charonsecurity.homora.checks.Finding
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.wifi.WifiSecurityInfo
import kotlinx.serialization.Serializable

/** A device the user has marked as theirs, with the name they gave it. */
@Serializable
data class KnownDevice(val key: String, val label: String)

/** The most recent completed scan, kept so the app opens with results. */
@Serializable
data class StoredScan(
    val at: Long,
    val durationMs: Long,
    val devices: List<Device>,
    val findings: List<Finding>,
    val wifi: WifiSecurityInfo? = null,
)

/** A saved spot from the Wi-Fi meter. */
@Serializable
data class RoomReading(val name: String, val rssi: Int, val latencyMs: Double? = null, val band: String? = null, val at: Long)

@Serializable
enum class HistoryKind { NEW_DEVICE, ISSUE_FOUND, ISSUE_FIXED }

/** One line of "Recent changes". [subject] is a device name or a FindingType name. */
@Serializable
data class HistoryEvent(val at: Long, val kind: HistoryKind, val subject: String)

/** Everything the app stores, in one private file on the phone. */
@Serializable
data class AppState(
    val known: Map<String, KnownDevice> = emptyMap(),
    val seenKeys: Set<String> = emptySet(),
    val lastScan: StoredScan? = null,
    val rooms: List<RoomReading> = emptyList(),
    val history: List<HistoryEvent> = emptyList(),
)

sealed interface ScanState {
    data object Idle : ScanState
    data class Running(val progress: Scanner.Progress) : ScanState
    data class Failed(val reason: Telemetry.ScanFailure) : ScanState
}
