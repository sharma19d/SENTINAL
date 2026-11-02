package com.charonsecurity.homora.checks

import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.DeviceKind

/**
 * A per-device risk score (0 = nothing to worry about, 100 = act now) and
 * the reasons behind it, so the UI can show a small badge first and the
 * "why" only when asked.
 */
object DeviceRisk {
    enum class Level { LOW, MEDIUM, HIGH }

    enum class Reason { HIGH_ISSUE, MEDIUM_ISSUE, LOW_ISSUE, NOT_MARKED, NEW_DEVICE, NO_NAME, SMART_DEVICE, MANY_SERVICES }

    data class Assessment(val score: Int, val level: Level, val reasons: List<Reason>)

    private val NONE = Assessment(0, Level.LOW, emptyList())

    fun assess(d: Device, findings: List<Finding>, marked: Boolean, isNew: Boolean): Assessment {
        if (d.isSelf) return NONE
        var s = 0
        val why = ArrayList<Reason>()
        val mine = findings.filter { it.deviceKey == d.identityKey }
        mine.count { it.type.severity == Severity.HIGH }.takeIf { it > 0 }?.let { s += 45 * it; why += Reason.HIGH_ISSUE }
        mine.count { it.type.severity == Severity.MEDIUM }.takeIf { it > 0 }?.let { s += 22 * it; why += Reason.MEDIUM_ISSUE }
        mine.count { it.type.severity == Severity.LOW }.takeIf { it > 0 }?.let { s += 8 * it; why += Reason.LOW_ISSUE }
        if (!marked) { s += 15; why += Reason.NOT_MARKED }
        if (isNew && !marked) { s += 10; why += Reason.NEW_DEVICE }
        if (!d.isGateway && d.isUnidentified) { s += 5; why += Reason.NO_NAME }
        if (d.kind == DeviceKind.CAMERA || d.kind == DeviceKind.SMART_HOME) { s += 5; why += Reason.SMART_DEVICE }
        if (d.openPorts.size >= 5) { s += 5; why += Reason.MANY_SERVICES }
        val score = s.coerceIn(0, 100)
        return Assessment(score, level(score), why)
    }

    fun level(score: Int): Level = when {
        score >= 45 -> Level.HIGH
        score >= 20 -> Level.MEDIUM
        else -> Level.LOW
    }
}

/**
 * Short, practical ways to keep a device from being a way into the rest of
 * the home network. Chosen from what the device is and what it exposes.
 */
object Isolation {
    enum class Advice { GUEST_NETWORK, CHANGE_PASSWORD, UPDATE_FIRMWARE, CLOSE_REMOTE_ACCESS, TURN_OFF_UPNP, CAMERA_CLOUD, IDENTIFY_FIRST, KEEP_ROUTER_UPDATED }

    fun advise(d: Device, findings: List<Finding>, marked: Boolean): List<Advice> {
        if (d.isSelf) return emptyList()
        val types = findings.filter { it.deviceKey == d.identityKey }.map { it.type }.toSet()
        val out = LinkedHashSet<Advice>()
        if (d.isGateway) {
            out += Advice.KEEP_ROUTER_UPDATED
            out += Advice.CHANGE_PASSWORD
            if (FindingType.UPNP_ON in types) out += Advice.TURN_OFF_UPNP
            return out.toList()
        }
        if (!marked) out += Advice.IDENTIFY_FIRST
        val iot = d.kind in setOf(DeviceKind.CAMERA, DeviceKind.SMART_HOME, DeviceKind.SPEAKER, DeviceKind.TV, DeviceKind.PRINTER, DeviceKind.UNKNOWN)
        if (iot) out += Advice.GUEST_NETWORK
        if (types.any { it == FindingType.TELNET_OPEN || it == FindingType.FTP_OPEN || it == FindingType.VNC_OPEN }) out += Advice.CLOSE_REMOTE_ACCESS
        if (d.kind == DeviceKind.CAMERA || FindingType.CAMERA_STREAM_OPEN in types) out += Advice.CAMERA_CLOUD
        if (iot || types.isNotEmpty()) {
            out += Advice.CHANGE_PASSWORD
            out += Advice.UPDATE_FIRMWARE
        }
        return out.toList()
    }
}
