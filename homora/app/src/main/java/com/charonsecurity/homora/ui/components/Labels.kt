package com.charonsecurity.homora.ui.components

import android.text.format.DateUtils
import androidx.annotation.ArrayRes
import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.Lightbulb
import androidx.compose.material.icons.outlined.Print
import androidx.compose.material.icons.outlined.Router
import androidx.compose.material.icons.outlined.SmartDisplay
import androidx.compose.material.icons.outlined.Smartphone
import androidx.compose.material.icons.outlined.SportsEsports
import androidx.compose.material.icons.outlined.Storage
import androidx.compose.material.icons.outlined.Videocam
import androidx.compose.material.icons.outlined.Speaker
import androidx.compose.material.icons.outlined.Cast
import androidx.compose.material.icons.outlined.DesktopWindows
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.Hub
import androidx.compose.material.icons.outlined.Lan
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.PhoneIphone
import androidx.compose.material.icons.outlined.QuestionMark
import androidx.compose.material.icons.outlined.Terminal
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.ui.graphics.vector.ImageVector
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.CheckId
import com.charonsecurity.homora.checks.FindingType
import com.charonsecurity.homora.checks.Severity
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.DeviceKind
import com.charonsecurity.homora.wifi.SignalZone

data class FindingText(@param:StringRes val title: Int, @param:StringRes val why: Int, @param:ArrayRes val steps: Int)

fun FindingType.text(): FindingText = when (this) {
    FindingType.WIFI_OPEN -> FindingText(R.string.f_wifi_open_title, R.string.f_wifi_open_why, R.array.f_wifi_open_steps)
    FindingType.WIFI_WEP -> FindingText(R.string.f_wifi_wep_title, R.string.f_wifi_wep_why, R.array.f_wifi_wep_steps)
    FindingType.WIFI_OLD_WPA -> FindingText(R.string.f_wifi_old_wpa_title, R.string.f_wifi_old_wpa_why, R.array.f_wifi_old_wpa_steps)
    FindingType.WPS_ON -> FindingText(R.string.f_wps_on_title, R.string.f_wps_on_why, R.array.f_wps_on_steps)
    FindingType.UPNP_ON -> FindingText(R.string.f_upnp_on_title, R.string.f_upnp_on_why, R.array.f_upnp_on_steps)
    FindingType.TELNET_OPEN -> FindingText(R.string.f_telnet_open_title, R.string.f_telnet_open_why, R.array.f_telnet_open_steps)
    FindingType.FTP_OPEN -> FindingText(R.string.f_ftp_open_title, R.string.f_ftp_open_why, R.array.f_ftp_open_steps)
    FindingType.VNC_OPEN -> FindingText(R.string.f_vnc_open_title, R.string.f_vnc_open_why, R.array.f_vnc_open_steps)
    FindingType.CAMERA_STREAM_OPEN -> FindingText(R.string.f_camera_stream_open_title, R.string.f_camera_stream_open_why, R.array.f_camera_stream_open_steps)
    FindingType.ROUTER_ADMIN_UNENCRYPTED -> FindingText(R.string.f_router_admin_unencrypted_title, R.string.f_router_admin_unencrypted_why, R.array.f_router_admin_unencrypted_steps)
}

@StringRes
fun CheckId.label(): Int = when (this) {
    CheckId.WIFI_ENCRYPTION -> R.string.check_wifi_encryption
    CheckId.WPS -> R.string.check_wps
    CheckId.UPNP -> R.string.check_upnp
    CheckId.TELNET -> R.string.check_telnet
    CheckId.FTP -> R.string.check_ftp
    CheckId.REMOTE_SCREEN -> R.string.check_remote_screen
    CheckId.CAMERA_STREAM -> R.string.check_camera_stream
    CheckId.ROUTER_ADMIN -> R.string.check_router_admin
}

@StringRes
fun Severity.label(): Int = when (this) {
    Severity.HIGH -> R.string.severity_high
    Severity.MEDIUM -> R.string.severity_medium
    Severity.LOW -> R.string.severity_low
}

@StringRes
fun DeviceKind.label(): Int = when (this) {
    DeviceKind.ROUTER -> R.string.kind_router
    DeviceKind.THIS_PHONE -> R.string.kind_this_phone
    DeviceKind.PHONE -> R.string.kind_phone
    DeviceKind.COMPUTER -> R.string.kind_computer
    DeviceKind.TV -> R.string.kind_tv
    DeviceKind.SPEAKER -> R.string.kind_speaker
    DeviceKind.CAMERA -> R.string.kind_camera
    DeviceKind.PRINTER -> R.string.kind_printer
    DeviceKind.SMART_HOME -> R.string.kind_smart_home
    DeviceKind.GAME_CONSOLE -> R.string.kind_console
    DeviceKind.STORAGE -> R.string.kind_storage
    DeviceKind.UNKNOWN -> R.string.kind_unknown
}

fun DeviceKind.icon(): ImageVector = when (this) {
    DeviceKind.ROUTER -> Icons.Outlined.Router
    DeviceKind.THIS_PHONE, DeviceKind.PHONE -> Icons.Outlined.Smartphone
    DeviceKind.COMPUTER -> Icons.Outlined.Computer
    DeviceKind.TV -> Icons.Outlined.SmartDisplay
    DeviceKind.SPEAKER -> Icons.Outlined.Speaker
    DeviceKind.CAMERA -> Icons.Outlined.Videocam
    DeviceKind.PRINTER -> Icons.Outlined.Print
    DeviceKind.SMART_HOME -> Icons.Outlined.Lightbulb
    DeviceKind.GAME_CONSOLE -> Icons.Outlined.SportsEsports
    DeviceKind.STORAGE -> Icons.Outlined.Storage
    DeviceKind.UNKNOWN -> Icons.Outlined.QuestionMark
}

@StringRes
fun SignalZone.label(): Int = when (this) {
    SignalZone.EXCELLENT -> R.string.zone_excellent
    SignalZone.GOOD -> R.string.zone_good
    SignalZone.FAIR -> R.string.zone_fair
    SignalZone.WEAK -> R.string.zone_weak
    SignalZone.DEAD -> R.string.zone_dead
}

@StringRes
fun SignalZone.roomAdvice(): Int = when (this) {
    SignalZone.EXCELLENT -> R.string.room_excellent
    SignalZone.GOOD -> R.string.room_good
    SignalZone.FAIR -> R.string.room_fair
    SignalZone.WEAK -> R.string.room_weak
    SignalZone.DEAD -> R.string.room_dead
}

/** Where a device's identity came from, for the detail screen. */
@StringRes
fun Device.identitySource(): Int = when (identityKey.substringBefore(':')) {
    "upnp" -> R.string.src_upnp
    "mdns" -> R.string.src_mdns
    "netbios" -> R.string.src_netbios
    "dns" -> R.string.src_dns
    "svc" -> R.string.src_service
    else -> R.string.src_ip
}

fun relativeTime(at: Long): String =
    DateUtils.getRelativeTimeSpanString(at, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS).toString()

/** Port numbers shown to people as the service they belong to. */
fun portName(port: Int): String = when (port) {
    21 -> "FTP (21)"
    22 -> "SSH (22)"
    23, 2323 -> "Telnet ($port)"
    80, 8080 -> "Web page ($port)"
    443, 8443 -> "Secure web page ($port)"
    139, 445 -> "File sharing ($port)"
    554 -> "Video stream (554)"
    1883 -> "MQTT (1883)"
    3389 -> "Remote desktop (3389)"
    5000 -> "Web / UPnP (5000)"
    5900 -> "Screen sharing (5900)"
    7000 -> "AirPlay (7000)"
    8008, 8009 -> "Cast ($port)"
    9100 -> "Printing (9100)"
    49152 -> "UPnP (49152)"
    62078 -> "Apple sync (62078)"
    else -> port.toString()
}

/** A short name and icon for an open port, for the service tiles on a device. */
data class ServiceInfo(val short: String, val icon: ImageVector, val risky: Boolean)

fun serviceInfo(port: Int): ServiceInfo = when (port) {
    21 -> ServiceInfo("FTP", Icons.Outlined.FolderOpen, true)
    22 -> ServiceInfo("SSH", Icons.Outlined.Terminal, false)
    23, 2323 -> ServiceInfo("Telnet", Icons.Outlined.Terminal, true)
    80, 8080 -> ServiceInfo("Web", Icons.Outlined.Language, false)
    443, 8443 -> ServiceInfo("HTTPS", Icons.Outlined.Lock, false)
    139, 445 -> ServiceInfo("Files", Icons.Outlined.Folder, false)
    554 -> ServiceInfo("Video", Icons.Outlined.Videocam, true)
    1883 -> ServiceInfo("MQTT", Icons.Outlined.Hub, false)
    3389 -> ServiceInfo("RDP", Icons.Outlined.DesktopWindows, true)
    5000, 49152 -> ServiceInfo("UPnP", Icons.Outlined.Wifi, false)
    5900 -> ServiceInfo("VNC", Icons.Outlined.DesktopWindows, true)
    7000 -> ServiceInfo("AirPlay", Icons.Outlined.Cast, false)
    8008, 8009 -> ServiceInfo("Cast", Icons.Outlined.Cast, false)
    9100 -> ServiceInfo("Print", Icons.Outlined.Print, false)
    62078 -> ServiceInfo("Apple", Icons.Outlined.PhoneIphone, false)
    else -> ServiceInfo(port.toString(), Icons.Outlined.Lan, false)
}

@StringRes
fun com.charonsecurity.homora.checks.DeviceRisk.Level.label(): Int = when (this) {
    com.charonsecurity.homora.checks.DeviceRisk.Level.LOW -> R.string.risk_low
    com.charonsecurity.homora.checks.DeviceRisk.Level.MEDIUM -> R.string.risk_medium
    com.charonsecurity.homora.checks.DeviceRisk.Level.HIGH -> R.string.risk_high
}

@StringRes
fun com.charonsecurity.homora.checks.DeviceRisk.Reason.label(): Int = when (this) {
    com.charonsecurity.homora.checks.DeviceRisk.Reason.HIGH_ISSUE -> R.string.risk_r_high
    com.charonsecurity.homora.checks.DeviceRisk.Reason.MEDIUM_ISSUE -> R.string.risk_r_medium
    com.charonsecurity.homora.checks.DeviceRisk.Reason.LOW_ISSUE -> R.string.risk_r_low
    com.charonsecurity.homora.checks.DeviceRisk.Reason.NOT_MARKED -> R.string.risk_r_not_marked
    com.charonsecurity.homora.checks.DeviceRisk.Reason.NEW_DEVICE -> R.string.risk_r_new
    com.charonsecurity.homora.checks.DeviceRisk.Reason.NO_NAME -> R.string.risk_r_no_name
    com.charonsecurity.homora.checks.DeviceRisk.Reason.SMART_DEVICE -> R.string.risk_r_smart
    com.charonsecurity.homora.checks.DeviceRisk.Reason.MANY_SERVICES -> R.string.risk_r_services
}

/** Title and one-paragraph body for a piece of isolation advice. */
fun com.charonsecurity.homora.checks.Isolation.Advice.text(): Pair<Int, Int> = when (this) {
    com.charonsecurity.homora.checks.Isolation.Advice.GUEST_NETWORK -> R.string.iso_guest_title to R.string.iso_guest_body
    com.charonsecurity.homora.checks.Isolation.Advice.CHANGE_PASSWORD -> R.string.iso_password_title to R.string.iso_password_body
    com.charonsecurity.homora.checks.Isolation.Advice.UPDATE_FIRMWARE -> R.string.iso_update_title to R.string.iso_update_body
    com.charonsecurity.homora.checks.Isolation.Advice.CLOSE_REMOTE_ACCESS -> R.string.iso_remote_title to R.string.iso_remote_body
    com.charonsecurity.homora.checks.Isolation.Advice.TURN_OFF_UPNP -> R.string.iso_upnp_title to R.string.iso_upnp_body
    com.charonsecurity.homora.checks.Isolation.Advice.CAMERA_CLOUD -> R.string.iso_camera_title to R.string.iso_camera_body
    com.charonsecurity.homora.checks.Isolation.Advice.IDENTIFY_FIRST -> R.string.iso_identify_title to R.string.iso_identify_body
    com.charonsecurity.homora.checks.Isolation.Advice.KEEP_ROUTER_UPDATED -> R.string.iso_router_title to R.string.iso_router_body
}
