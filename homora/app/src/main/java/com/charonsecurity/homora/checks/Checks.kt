package com.charonsecurity.homora.checks

import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.wifi.WifiSecurity
import com.charonsecurity.homora.wifi.WifiSecurityInfo
import kotlinx.serialization.Serializable

enum class Severity { HIGH, MEDIUM, LOW }

/**
 * Every check the app runs. Each one is something the owner can fix; a check
 * with no fix the user can act on doesn't belong here.
 */
enum class CheckId { WIFI_ENCRYPTION, WPS, UPNP, TELNET, FTP, REMOTE_SCREEN, CAMERA_STREAM, ROUTER_ADMIN }

@Serializable
enum class FindingType(val check: CheckId, val severity: Severity) {
    WIFI_OPEN(CheckId.WIFI_ENCRYPTION, Severity.HIGH),
    WIFI_WEP(CheckId.WIFI_ENCRYPTION, Severity.HIGH),
    WIFI_OLD_WPA(CheckId.WIFI_ENCRYPTION, Severity.HIGH),
    WPS_ON(CheckId.WPS, Severity.MEDIUM),
    UPNP_ON(CheckId.UPNP, Severity.MEDIUM),
    TELNET_OPEN(CheckId.TELNET, Severity.HIGH),
    FTP_OPEN(CheckId.FTP, Severity.MEDIUM),
    VNC_OPEN(CheckId.REMOTE_SCREEN, Severity.MEDIUM),
    CAMERA_STREAM_OPEN(CheckId.CAMERA_STREAM, Severity.LOW),
    ROUTER_ADMIN_UNENCRYPTED(CheckId.ROUTER_ADMIN, Severity.LOW),
}

/** One problem, optionally on one device. [id] is stable across scans for "fixed since last time". */
@Serializable
data class Finding(val type: FindingType, val deviceKey: String? = null, val deviceName: String? = null, val deviceIp: String? = null) {
    val id: String get() = type.name + (deviceKey?.let { "@$it" } ?: "")
}

data class SecurityReport(val findings: List<Finding>, val passed: List<CheckId>)

object Checks {

    fun evaluate(devices: List<Device>, wifi: WifiSecurityInfo?): SecurityReport {
        val findings = ArrayList<Finding>()
        val evaluated = HashSet<CheckId>()

        if (wifi != null && wifi.security != WifiSecurity.UNKNOWN) {
            evaluated += CheckId.WIFI_ENCRYPTION
            when (wifi.security) {
                WifiSecurity.OPEN -> findings += Finding(FindingType.WIFI_OPEN)
                WifiSecurity.WEP -> findings += Finding(FindingType.WIFI_WEP)
                WifiSecurity.WPA_OLD -> findings += Finding(FindingType.WIFI_OLD_WPA)
                else -> {}
            }
        }
        if (wifi?.wpsEnabled != null) {
            evaluated += CheckId.WPS
            if (wifi.wpsEnabled) findings += Finding(FindingType.WPS_ON)
        }

        val others = devices.filter { !it.isSelf }
        if (others.isNotEmpty()) {
            evaluated += listOf(CheckId.UPNP, CheckId.TELNET, CheckId.FTP, CheckId.REMOTE_SCREEN, CheckId.CAMERA_STREAM)
        }
        for (d in others) {
            fun add(type: FindingType) { findings += Finding(type, d.identityKey, d.bestName, d.ip) }
            if (Scanner.UPNP_IGD in d.services) add(FindingType.UPNP_ON)
            if (23 in d.openPorts || 2323 in d.openPorts) add(FindingType.TELNET_OPEN)
            if (21 in d.openPorts) add(FindingType.FTP_OPEN)
            if (5900 in d.openPorts) add(FindingType.VNC_OPEN)
            if (554 in d.openPorts) add(FindingType.CAMERA_STREAM_OPEN)
            if (d.isGateway) {
                evaluated += CheckId.ROUTER_ADMIN
                if (80 in d.openPorts && 443 !in d.openPorts && 8443 !in d.openPorts) add(FindingType.ROUTER_ADMIN_UNENCRYPTED)
            }
        }

        val sorted = findings.sortedWith(compareBy({ it.type.severity.ordinal }, { it.type.ordinal }))
        val failed = sorted.map { it.type.check }.toSet()
        return SecurityReport(sorted, CheckId.entries.filter { it in evaluated && it !in failed })
    }
}
