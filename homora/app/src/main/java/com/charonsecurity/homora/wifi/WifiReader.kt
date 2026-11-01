package com.charonsecurity.homora.wifi

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.Build
import com.charonsecurity.homora.net.Ipv4
import com.charonsecurity.homora.net.LanInfo
import java.net.DatagramSocket
import java.net.Inet4Address

/** Reads the phone's own Wi-Fi state. Nothing here leaves the device. */
class WifiReader(context: Context) {
    private val wifi = context.applicationContext.getSystemService(WifiManager::class.java)
    private val cm = context.applicationContext.getSystemService(ConnectivityManager::class.java)

    /** The Wi-Fi network, even when Android routes internet over mobile data. */
    @Suppress("DEPRECATION")
    fun wifiNetwork(): Network? {
        val active = cm.activeNetwork
        if (active != null && cm.getNetworkCapabilities(active)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true) return active
        return cm.allNetworks.firstOrNull { cm.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true }
    }

    fun lanInfo(): LanInfo? {
        val net = wifiNetwork() ?: return null
        val lp: LinkProperties = cm.getLinkProperties(net) ?: return null
        val link = lp.linkAddresses.firstOrNull { it.address is Inet4Address } ?: return null
        val self = Ipv4.fromBytes(link.address.address) ?: return null
        val gateway = lp.routes.firstOrNull { it.isDefaultRoute && it.gateway is Inet4Address }
            ?.gateway?.address?.let(Ipv4::fromBytes)?.takeIf { it != 0 }
        val dns = lp.dnsServers.filterIsInstance<Inet4Address>().mapNotNull { Ipv4.fromBytes(it.address) }
        return LanInfo(self, link.prefixLength, gateway, dns)
    }

    @Suppress("DEPRECATION")
    fun connection(): Connection? {
        if (wifiNetwork() == null) return null
        val info = wifi.connectionInfo ?: return null
        if (info.networkId == -1 && info.rssi <= -127) return null
        val ssid = info.ssid?.removeSurrounding("\"")?.takeIf { it.isNotBlank() && it != "<unknown ssid>" }
        val bssid = info.bssid?.takeIf { it != "02:00:00:00:00:00" }
        val secType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) info.currentSecurityType.takeIf { it >= 0 } else null
        return Connection(info.rssi, info.linkSpeed, info.frequency, ssid, bssid, secType)
    }

    /** The last scan Android already has. Empty without location permission. */
    @Suppress("DEPRECATION")
    fun accessPoints(): List<AccessPoint> = try {
        wifi.scanResults.orEmpty().map {
            AccessPoint(it.SSID?.takeIf(String::isNotBlank), it.BSSID ?: "", it.frequency, it.level, it.capabilities ?: "")
        }
    } catch (_: SecurityException) {
        emptyList()
    }

    /** Asks for a fresh scan. Android allows only a few per two minutes, so call it sparingly. */
    @Suppress("DEPRECATION")
    fun requestScan(): Boolean = try {
        wifi.startScan()
    } catch (_: SecurityException) {
        false
    }

    /** Sends UDP discovery over Wi-Fi even when mobile data is the default route. */
    fun bindToWifi(socket: DatagramSocket) {
        try {
            wifiNetwork()?.bindSocket(socket)
        } catch (_: Exception) {
        }
    }
}
