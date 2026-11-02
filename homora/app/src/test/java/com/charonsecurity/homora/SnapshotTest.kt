package com.charonsecurity.homora

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.ui.components.HomoraLogo
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.charonsecurity.homora.checks.Checks
import com.charonsecurity.homora.data.AppState
import com.charonsecurity.homora.data.HistoryEvent
import com.charonsecurity.homora.data.HistoryKind
import com.charonsecurity.homora.data.KnownDevice
import com.charonsecurity.homora.data.RoomReading
import com.charonsecurity.homora.data.StoredScan
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.ui.HomoraRoot
import com.charonsecurity.homora.ui.devices.DeviceDetailScreen
import com.charonsecurity.homora.ui.security.FindingScreen
import com.charonsecurity.homora.ui.settings.SettingsScreen
import com.charonsecurity.homora.ui.theme.HomoraTheme
import com.charonsecurity.homora.ui.wifi.WifiContent
import com.charonsecurity.homora.wifi.Connection
import com.charonsecurity.homora.wifi.WifiSecurity
import com.charonsecurity.homora.wifi.WifiSecurityInfo
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.runBlocking
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Renders real screens with realistic data to PNG (Robolectric + Roborazzi),
 * so the UI can be reviewed without a phone. Images are written only with
 * `-Psnapshots`, to app/snapshots/.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi", application = Application::class)
class SnapshotTest {
    @get:Rule val compose = createComposeRule()

    private val now = 1_761_990_000_000L
    private val router = Device("192.168.1.1", upnpName = "Archer C6", manufacturer = "TP-Link", openPorts = setOf(80), services = setOf(Scanner.UPNP_IGD), isGateway = true)
    private val self = Device("192.168.1.23", isSelf = true)
    private val tv = Device("192.168.1.30", mdnsInstance = "Living Room TV", mdnsHost = "tv.local", model = "Chromecast", services = setOf("_googlecast._tcp.local"), openPorts = setOf(8008, 8009))
    private val camera = Device("192.168.1.41", upnpUuid = "cam-1", upnpName = "Hall camera", manufacturer = "Generic", model = "IPC-200", openPorts = setOf(23, 80, 554))
    private val iphone = Device("192.168.1.52", mdnsHost = "Vinays-iPhone.local", openPorts = setOf(62078))
    private val printer = Device("192.168.1.60", mdnsInstance = "HP LaserJet M110", services = setOf("_ipp._tcp.local"), openPorts = setOf(80, 9100))
    private val plug = Device("192.168.1.71", dnsName = "ESP_3A2B1C.lan", openPorts = setOf(80))
    private val mystery = Device("192.168.1.88")
    private val devices = listOf(self, router, tv, camera, iphone, printer, plug, mystery)
    private val wifi = WifiSecurityInfo(WifiSecurity.WPA2, wpsEnabled = true)

    private fun container(onboarded: Boolean = true, scanned: Boolean = true): AppContainer {
        val c = AppContainer(RuntimeEnvironment.getApplication())
        if (onboarded) c.prefs.setOnboarded()
        if (scanned) {
            val findings = Checks.evaluate(devices, wifi).findings
            runBlocking {
                c.store.update {
                    AppState(
                        known = mapOf(
                            tv.identityKey to KnownDevice(tv.identityKey, "Living room TV"),
                            iphone.identityKey to KnownDevice(iphone.identityKey, "Vinay's iPhone"),
                            printer.identityKey to KnownDevice(printer.identityKey, "Printer"),
                        ),
                        seenKeys = devices.map { it.identityKey }.toSet(),
                        lastScan = StoredScan(now - 4 * 60_000, 21_000, devices, findings, wifi),
                        rooms = listOf(
                            RoomReading("Living room", -48, 3.1, "5 GHz", now),
                            RoomReading("Bedroom", -63, 4.0, "5 GHz", now),
                            RoomReading("Kitchen", -78, 9.5, "2.4 GHz", now),
                        ),
                        history = listOf(
                            HistoryEvent(now - 3_600_000, HistoryKind.NEW_DEVICE, "ESP_3A2B1C"),
                            HistoryEvent(now - 86_400_000, HistoryKind.ISSUE_FIXED, "WIFI_OLD_WPA"),
                        ),
                    )
                }
            }
        }
        return c
    }

    private fun shot(name: String) = compose.onRoot().captureRoboImage("snapshots/$name.png")

    @Test fun home() {
        val c = container()
        compose.setContent { HomoraTheme { HomoraRoot(c) } }
        shot("01_home")
    }

    @Test fun devices() {
        val c = container()
        compose.setContent { HomoraTheme { HomoraRoot(c) } }
        compose.onNodeWithContentDescription("Devices").performClick()
        compose.waitForIdle()
        shot("02_devices")
    }

    @Test fun security() {
        val c = container()
        compose.setContent { HomoraTheme { HomoraRoot(c) } }
        compose.onNodeWithContentDescription("Security").performClick()
        compose.waitForIdle()
        shot("03_security")
    }

    @Test fun finding() {
        val c = container()
        val id = Checks.evaluate(devices, wifi).findings.first().id
        compose.setContent { HomoraTheme { FindingScreen(c, id, onBack = {}, onRescan = {}) } }
        shot("04_finding")
    }

    @Test fun unknownDevice() {
        val c = container()
        compose.setContent { HomoraTheme { DeviceDetailScreen(c, mystery.identityKey, onBack = {}, onIdentify = {}, onFinding = {}) } }
        shot("05_unknown_device")
    }

    @Test fun wifiMeter() {
        val c = container()
        val samples = listOf(-71, -70, -69, -68, -66, -66, -64, -63, -61, -60, -58, -57, -57, -56, -55, -55, -54, -54, -53, -52)
        compose.setContent {
            HomoraTheme {
                Surface {
                    WifiContent(
                        connected = true,
                        conn = Connection(-53, 433, 5180, "Sharma Home", null, 2),
                        rssi = -53.0, trend = 1, latencyMs = 3.4, samples = samples, sound = false, hasPermission = true,
                        rooms = c.store.state.value.rooms,
                        onSaveSpot = {}, onSound = {}, onAllow = {}, onDeleteRoom = {}, onSmartHelper = {},
                    )
                }
            }
        }
        shot("06_wifi")
    }

    @Test @Config(qualifiers = "+night")
    fun wifiMeterDark() {
        val samples = listOf(-80, -82, -84, -83, -85, -86)
        compose.setContent {
            HomoraTheme {
                Surface {
                    WifiContent(
                        connected = true, conn = Connection(-86, 6, 2437, null, null, 2), rssi = -85.5, trend = -1, latencyMs = 41.0,
                        samples = samples, sound = true, hasPermission = false, rooms = emptyList(),
                        onSaveSpot = {}, onSound = {}, onAllow = {}, onDeleteRoom = {}, onSmartHelper = {},
                    )
                }
            }
        }
        shot("07_wifi_dark_weak")
    }

    /** The intro animation's frames: the logo drawing itself at a few points in time. */
    @Test fun logoAnimationFrames() {
        compose.setContent {
            HomoraTheme {
                Surface {
                    Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        listOf(0.2f, 0.45f, 0.7f, 1f).forEach { HomoraLogo(Modifier.size(80.dp), progress = it) }
                    }
                }
            }
        }
        shot("08_logo_frames")
    }

    @Test fun onboardingPages() {
        val c = container(onboarded = false, scanned = false)
        compose.setContent { HomoraTheme { HomoraRoot(c) } }
        // A tap skips the logo animation, as it does on a phone.
        compose.onRoot().performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Get started").fetchSemanticsNodes().isNotEmpty() }
        compose.waitForIdle()
        shot("08b_onboarding_page1")
        compose.onNodeWithText("Get started").performClick()
        compose.waitForIdle()
        shot("08c_onboarding_page2")
        compose.onNodeWithText("Skip").performClick()
        compose.waitForIdle()
        shot("08d_onboarding_privacy")
    }

    @Test fun settings() {
        val c = container()
        compose.setContent { HomoraTheme { SettingsScreen(c, onBack = {}, onFeedback = {}) } }
        shot("09_settings")
    }

    @Test fun firstRun() {
        val c = container(scanned = false)
        compose.setContent { HomoraTheme { HomoraRoot(c) } }
        shot("10_first_run")
    }
}
