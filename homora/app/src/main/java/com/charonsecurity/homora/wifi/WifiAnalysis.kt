package com.charonsecurity.homora.wifi

import kotlinx.serialization.Serializable

@Serializable
enum class WifiSecurity { OPEN, ENHANCED_OPEN, WEP, WPA_OLD, WPA2, WPA3, ENTERPRISE, UNKNOWN }

@Serializable
data class WifiSecurityInfo(val security: WifiSecurity, val wpsEnabled: Boolean?)

object WifiAnalysis {

    // android.net.wifi.WifiInfo.SECURITY_TYPE_* (API 31+)
    private const val ST_OPEN = 0
    private const val ST_WEP = 1
    private const val ST_PSK = 2
    private const val ST_EAP = 3
    private const val ST_SAE = 4
    private const val ST_EAP_192 = 5
    private const val ST_OWE = 6
    private const val ST_EAP_WPA3 = 9

    /**
     * Security of the network the phone is on. The scan entry for our own
     * access point ([capabilities]) is more detailed than the API's security
     * type (it separates old WPA from WPA2 and shows WPS), so it wins when present.
     */
    fun security(securityType: Int?, capabilities: String?): WifiSecurityInfo {
        if (capabilities != null) {
            val c = capabilities.uppercase()
            val sec = when {
                "EAP" in c -> WifiSecurity.ENTERPRISE
                "SAE" in c -> WifiSecurity.WPA3
                "RSN" in c || "WPA2" in c -> WifiSecurity.WPA2
                "WPA" in c -> WifiSecurity.WPA_OLD
                "WEP" in c -> WifiSecurity.WEP
                "OWE" in c -> WifiSecurity.ENHANCED_OPEN
                else -> WifiSecurity.OPEN
            }
            return WifiSecurityInfo(sec, "[WPS]" in c)
        }
        val sec = when (securityType) {
            ST_OPEN -> WifiSecurity.OPEN
            ST_WEP -> WifiSecurity.WEP
            ST_PSK -> WifiSecurity.WPA2 // the API does not separate old WPA from WPA2
            ST_SAE -> WifiSecurity.WPA3
            ST_OWE -> WifiSecurity.ENHANCED_OPEN
            ST_EAP, ST_EAP_192, ST_EAP_WPA3 -> WifiSecurity.ENTERPRISE
            else -> WifiSecurity.UNKNOWN
        }
        return WifiSecurityInfo(sec, null)
    }

    /** Finds our own access point in a scan, by BSSID, or by name and frequency when the BSSID is hidden. */
    fun ownAccessPoint(conn: Connection, aps: List<AccessPoint>): AccessPoint? =
        conn.bssid?.let { b -> aps.firstOrNull { it.bssid.equals(b, true) } }
            ?: conn.ssid?.let { s -> aps.firstOrNull { it.ssid == s && it.frequencyMhz == conn.frequencyMhz } }

    data class SmartDeviceReport(
        val currentBand: Band,
        /** True when the router uses one network name for 2.4 GHz and 5/6 GHz (band steering). */
        val sharedNameAcrossBands: Boolean?,
        /** Networks overlapping our 2.4 GHz channel (null if we can't see our 2.4 GHz radio). */
        val neighboursOnOurChannel: Int?,
        val ourChannel24: Int?,
        /** The least crowded of channels 1, 6 and 11, and how many networks overlap it. */
        val quietestChannel: Int?,
        val quietestCount: Int?,
    )

    /**
     * What gets in the way of setting up a 2.4 GHz-only smart device: the
     * phone being on 5 GHz, one name for both bands, and a crowded channel.
     */
    fun smartDevice(conn: Connection, aps: List<AccessPoint>): SmartDeviceReport {
        val ours = conn.ssid?.let { s -> aps.filter { it.ssid == s } }.orEmpty()
        val sharedName = if (conn.ssid == null) null else {
            val bands = ours.map { it.band }.toSet()
            Band.GHZ_2_4 in bands && (Band.GHZ_5 in bands || Band.GHZ_6 in bands)
        }
        val ourBssids = ours.map { it.bssid.lowercase() }.toSet()
        val others24 = aps.filter { it.band == Band.GHZ_2_4 && it.bssid.lowercase() !in ourBssids }
        fun overlapping(ch: Int) = others24.count { ap -> ap.channel?.let { kotlin.math.abs(it - ch) < 5 } == true }
        val our24 = ours.firstOrNull { it.band == Band.GHZ_2_4 }?.channel
            ?: if (conn.band == Band.GHZ_2_4) channelOf(conn.frequencyMhz) else null
        val quietest = listOf(1, 6, 11).minByOrNull(::overlapping)
        return SmartDeviceReport(
            currentBand = conn.band,
            sharedNameAcrossBands = sharedName,
            neighboursOnOurChannel = our24?.let(::overlapping),
            ourChannel24 = our24,
            quietestChannel = if (aps.isEmpty()) null else quietest,
            quietestCount = if (aps.isEmpty()) null else quietest?.let(::overlapping),
        )
    }
}
