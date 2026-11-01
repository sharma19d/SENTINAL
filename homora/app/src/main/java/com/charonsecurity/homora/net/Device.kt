package com.charonsecurity.homora.net

import kotlinx.serialization.Serializable

enum class DeviceKind { ROUTER, THIS_PHONE, PHONE, COMPUTER, TV, SPEAKER, CAMERA, PRINTER, SMART_HOME, GAME_CONSOLE, STORAGE, UNKNOWN }

/**
 * Everything a scan learned about one address. Android 10+ hides other
 * devices' MAC addresses from apps, so identity comes from what a device
 * announces about itself (mDNS, UPnP, NetBIOS, router DNS, its web page).
 */
@Serializable
data class Device(
    val ip: String,
    val upnpUuid: String? = null,
    val upnpName: String? = null,
    val manufacturer: String? = null,
    val model: String? = null,
    val mdnsHost: String? = null,
    val mdnsInstance: String? = null,
    val netbiosName: String? = null,
    val dnsName: String? = null,
    val httpTitle: String? = null,
    val httpServer: String? = null,
    val services: Set<String> = emptySet(),
    val openPorts: Set<Int> = emptySet(),
    val isGateway: Boolean = false,
    val isSelf: Boolean = false,
) {
    /**
     * A key that stays the same when the router hands out a new IP address,
     * so "this is mine" survives between scans. Falls back to the IP only when
     * the device announces nothing at all.
     */
    val identityKey: String
        get() = when {
            isSelf -> "self"
            isGateway -> "gateway"
            upnpUuid != null -> "upnp:$upnpUuid"
            mdnsHost != null -> "mdns:${mdnsHost.lowercase()}"
            netbiosName != null -> "netbios:${netbiosName.lowercase()}"
            dnsName != null -> "dns:${dnsName.lowercase()}"
            mdnsInstance != null -> "svc:${mdnsInstance.lowercase()}"
            else -> "ip:$ip"
        }

    /** True when we have nothing better than the IP address to recognise it by. */
    val isUnidentified: Boolean get() = identityKey.startsWith("ip:")

    /** The best human-readable name we have, or null. */
    val bestName: String?
        get() = listOfNotNull(
            upnpName, mdnsInstance, mdnsHost?.removeSuffix(".local"), netbiosName,
            dnsName?.let(::shortDnsName), model?.let { m -> listOfNotNull(manufacturer, m).joinToString(" ") }, httpTitle,
        ).firstOrNull { it.isNotBlank() }

    val kind: DeviceKind get() = guessKind(this)
}

private fun shortDnsName(name: String): String =
    name.removeSuffix(".").split('.').first()

private val CAMERA_WORDS = listOf("camera", "cam", "ipc", "nvr", "dvr", "hikvision", "dahua", "reolink", "wyze", "imou", "ezviz", "tapo c")
private val TV_WORDS = listOf("tv", "bravia", "roku", "fire tv", "chromecast", "shield", "android tv", "webos", "tizen")
private val PHONE_WORDS = listOf("iphone", "ipad", "android", "galaxy", "pixel", "redmi", "oneplus", "vivo", "oppo", "realme", "phone")
private val COMPUTER_WORDS = listOf("macbook", "imac", "laptop", "desktop", "pc", "windows", "thinkpad", "workstation")
private val PRINTER_WORDS = listOf("printer", "laserjet", "deskjet", "officejet", "epson", "canon", "brother")
private val SPEAKER_WORDS = listOf("echo", "alexa", "sonos", "homepod", "speaker", "nest mini", "google home")
private val CONSOLE_WORDS = listOf("playstation", "ps4", "ps5", "xbox", "nintendo")
private val SMART_WORDS = listOf("plug", "bulb", "light", "switch", "tuya", "smart life", "shelly", "tasmota", "esp", "hue", "nest", "thermostat", "doorbell", "matter", "vacuum", "roborock")

internal fun guessKind(d: Device): DeviceKind {
    if (d.isSelf) return DeviceKind.THIS_PHONE
    if (d.isGateway) return DeviceKind.ROUTER
    val text = listOfNotNull(d.upnpName, d.manufacturer, d.model, d.mdnsHost, d.mdnsInstance, d.netbiosName, d.dnsName, d.httpTitle, d.httpServer)
        .joinToString(" ").lowercase()
    val s = d.services
    fun has(vararg types: String) = types.any { t -> s.any { it.startsWith(t) } }
    fun says(words: List<String>) = words.any { w -> Regex("(^|[^a-z])${Regex.escape(w)}([^a-z]|$)").containsMatchIn(text) }
    return when {
        d.openPorts.contains(554) || says(CAMERA_WORDS) -> DeviceKind.CAMERA
        has("_ipp.", "_printer.", "_pdl-datastream.") || d.openPorts.contains(9100) || says(PRINTER_WORDS) -> DeviceKind.PRINTER
        has("_googlecast.", "_androidtvremote", "_amzn-wplay.", "_viziocast.") || says(TV_WORDS) -> DeviceKind.TV
        has("_spotify-connect.", "_sonos.", "_raop.") && !has("_companion-link.") || says(SPEAKER_WORDS) -> DeviceKind.SPEAKER
        says(CONSOLE_WORDS) -> DeviceKind.GAME_CONSOLE
        d.openPorts.contains(62078) || has("_companion-link.", "_apple-mobdev2.") || says(PHONE_WORDS) -> DeviceKind.PHONE
        has("_smb.", "_afpovertcp.") && says(listOf("nas", "synology", "qnap", "diskstation")) -> DeviceKind.STORAGE
        has("_hap.", "_matter.", "_matterc.", "_hue.", "_esphomelib.", "_miio.", "_shelly.") || says(SMART_WORDS) -> DeviceKind.SMART_HOME
        has("_workstation.", "_smb.", "_rfb.", "_ssh.", "_sftp-ssh.") || d.netbiosName != null || says(COMPUTER_WORDS) -> DeviceKind.COMPUTER
        else -> DeviceKind.UNKNOWN
    }
}
