package com.charonsecurity.homora.wifi

/** The phone's current Wi-Fi link. [ssid]/[bssid] are null without location permission. */
data class Connection(
    val rssi: Int,
    val linkMbps: Int,
    val frequencyMhz: Int,
    val ssid: String?,
    val bssid: String?,
    val securityType: Int?,
) {
    val band: Band get() = Band.of(frequencyMhz)
}

/** One access point from a Wi-Fi scan. Stays on the phone; never uploaded. */
data class AccessPoint(val ssid: String?, val bssid: String, val frequencyMhz: Int, val level: Int, val capabilities: String) {
    val band: Band get() = Band.of(frequencyMhz)
    val channel: Int? get() = channelOf(frequencyMhz)
}

enum class Band(val label: String) {
    GHZ_2_4("2.4 GHz"), GHZ_5("5 GHz"), GHZ_6("6 GHz"), UNKNOWN("–");

    companion object {
        fun of(mhz: Int) = when (mhz) {
            in 2400..2500 -> GHZ_2_4
            in 4900..5899 -> GHZ_5
            in 5925..7125 -> GHZ_6
            else -> UNKNOWN
        }
    }
}

fun channelOf(mhz: Int): Int? = when (mhz) {
    2484 -> 14
    in 2412..2472 -> (mhz - 2407) / 5
    in 5000..5899 -> (mhz - 5000) / 5
    in 5955..7115 -> (mhz - 5950) / 5
    else -> null
}

/** Signal zones on the meter. Thresholds are the usual rules of thumb, not a standard. */
enum class SignalZone(val minRssi: Int) {
    EXCELLENT(-50), GOOD(-60), FAIR(-70), WEAK(-80), DEAD(Int.MIN_VALUE);

    companion object {
        fun of(rssi: Int): SignalZone = entries.first { rssi >= it.minRssi }

        /** 0..1 for the gauge: -90 dBm and below is empty, -40 and above is full. */
        fun fraction(rssi: Double): Float = ((rssi + 90.0) / 50.0).coerceIn(0.0, 1.0).toFloat()
    }
}
