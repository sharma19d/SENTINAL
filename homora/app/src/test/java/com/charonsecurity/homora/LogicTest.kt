package com.charonsecurity.homora

import com.charonsecurity.homora.checks.CheckId
import com.charonsecurity.homora.checks.Checks
import com.charonsecurity.homora.checks.DeviceRisk
import com.charonsecurity.homora.checks.Isolation
import com.charonsecurity.homora.checks.Finding
import com.charonsecurity.homora.checks.FindingType
import com.charonsecurity.homora.checks.Health
import com.charonsecurity.homora.data.AppState
import com.charonsecurity.homora.data.HistoryKind
import com.charonsecurity.homora.data.blockedStillPresent
import com.charonsecurity.homora.data.ScanRepository
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.DeviceKind
import com.charonsecurity.homora.net.ScanOutcome
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.wifi.AccessPoint
import com.charonsecurity.homora.wifi.Band
import com.charonsecurity.homora.wifi.Connection
import com.charonsecurity.homora.wifi.SignalZone
import com.charonsecurity.homora.wifi.WifiAnalysis
import com.charonsecurity.homora.wifi.WifiSecurity
import com.charonsecurity.homora.wifi.WifiSecurityInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceTest {
    @Test fun identityPrefersStableAnnouncedNames() {
        assertEquals("upnp:u1", Device("192.168.1.5", upnpUuid = "u1", mdnsHost = "tv.local").identityKey)
        assertEquals("mdns:tv.local", Device("192.168.1.5", mdnsHost = "TV.local").identityKey)
        assertEquals("ip:192.168.1.5", Device("192.168.1.5").identityKey)
        assertTrue(Device("192.168.1.5").isUnidentified)
        assertEquals("gateway", Device("192.168.1.1", upnpUuid = "x", isGateway = true).identityKey)
    }

    @Test fun bestNameOrder() {
        assertEquals("Bedroom TV", Device("1", upnpName = "Bedroom TV", mdnsHost = "x.local").bestName)
        assertEquals("rahuls-laptop", Device("1", dnsName = "rahuls-laptop.lan.").bestName)
        assertNull(Device("1").bestName)
    }

    @Test fun kindGuesses() {
        assertEquals(DeviceKind.CAMERA, Device("1", openPorts = setOf(554, 80)).kind)
        assertEquals(DeviceKind.TV, Device("1", services = setOf("_googlecast._tcp.local")).kind)
        assertEquals(DeviceKind.PRINTER, Device("1", services = setOf("_ipp._tcp.local")).kind)
        assertEquals(DeviceKind.PHONE, Device("1", openPorts = setOf(62078)).kind)
        assertEquals(DeviceKind.SMART_HOME, Device("1", dnsName = "ESP_3A2B1C").kind)
        assertEquals(DeviceKind.SMART_HOME, Device("1", upnpName = "Smart Switch").kind)
        assertEquals(DeviceKind.COMPUTER, Device("1", netbiosName = "DESKTOP-ABC").kind)
        assertEquals(DeviceKind.ROUTER, Device("1", isGateway = true, openPorts = setOf(554)).kind)
        assertEquals(DeviceKind.UNKNOWN, Device("1").kind)
    }
}

class ChecksTest {
    private val router = Device("192.168.1.1", isGateway = true, openPorts = setOf(80, 53), services = setOf(Scanner.UPNP_IGD))
    private val camera = Device("192.168.1.9", upnpUuid = "cam", upnpName = "Hall Cam", openPorts = setOf(23, 554))
    private val phone = Device("192.168.1.20", isSelf = true)

    @Test fun findsIssuesSortedBySeverity() {
        val r = Checks.evaluate(listOf(phone, router, camera), WifiSecurityInfo(WifiSecurity.WPA2, wpsEnabled = true))
        val types = r.findings.map { it.type }
        assertEquals(FindingType.TELNET_OPEN, types.first())
        assertTrue(FindingType.UPNP_ON in types)
        assertTrue(FindingType.WPS_ON in types)
        assertTrue(FindingType.CAMERA_STREAM_OPEN in types)
        assertTrue(FindingType.ROUTER_ADMIN_UNENCRYPTED in types)
        assertTrue(CheckId.WIFI_ENCRYPTION in r.passed)
        assertFalse(CheckId.UPNP in r.passed)
        assertEquals("TELNET_OPEN@upnp:cam", r.findings.first().id)
        assertEquals("Hall Cam", r.findings.first().deviceName)
    }

    @Test fun nothingClaimedWithoutEvidence() {
        val r = Checks.evaluate(listOf(phone), null)
        assertTrue(r.findings.isEmpty())
        assertTrue(r.passed.isEmpty())
    }

    @Test fun weakWifi() {
        assertEquals(FindingType.WIFI_WEP, Checks.evaluate(emptyList(), WifiSecurityInfo(WifiSecurity.WEP, null)).findings.single().type)
        assertEquals(FindingType.WIFI_OPEN, Checks.evaluate(emptyList(), WifiSecurityInfo(WifiSecurity.OPEN, false)).findings.single().type)
    }
}

class WifiAnalysisTest {
    @Test fun securityFromCapabilities() {
        assertEquals(WifiSecurityInfo(WifiSecurity.WPA2, true), WifiAnalysis.security(2, "[WPA2-PSK-CCMP][RSN-PSK-CCMP][ESS][WPS]"))
        assertEquals(WifiSecurity.WPA3, WifiAnalysis.security(null, "[RSN-SAE-CCMP][ESS]").security)
        assertEquals(WifiSecurity.WPA_OLD, WifiAnalysis.security(null, "[WPA-PSK-TKIP][ESS]").security)
        assertEquals(WifiSecurity.WEP, WifiAnalysis.security(null, "[WEP][ESS]").security)
        assertEquals(WifiSecurity.OPEN, WifiAnalysis.security(null, "[ESS]").security)
        assertEquals(WifiSecurity.ENTERPRISE, WifiAnalysis.security(null, "[WPA2-EAP-CCMP][ESS]").security)
        assertEquals(WifiSecurityInfo(WifiSecurity.WPA3, null), WifiAnalysis.security(4, null))
    }

    @Test fun zones() {
        assertEquals(SignalZone.EXCELLENT, SignalZone.of(-45))
        assertEquals(SignalZone.GOOD, SignalZone.of(-60))
        assertEquals(SignalZone.FAIR, SignalZone.of(-65))
        assertEquals(SignalZone.WEAK, SignalZone.of(-79))
        assertEquals(SignalZone.DEAD, SignalZone.of(-85))
        assertEquals(0f, SignalZone.fraction(-95.0))
        assertEquals(1f, SignalZone.fraction(-30.0))
    }

    @Test fun smartDeviceReport() {
        val conn = Connection(-55, 433, 5180, "Home", "aa:aa:aa:aa:aa:02", 2)
        val aps = listOf(
            AccessPoint("Home", "aa:aa:aa:aa:aa:01", 2437, -50, "[WPA2-PSK-CCMP]"),
            AccessPoint("Home", "aa:aa:aa:aa:aa:02", 5180, -55, "[WPA2-PSK-CCMP]"),
        ) + (1..6).map { AccessPoint("N$it", "bb:00:00:00:00:0$it", 2437, -70, "") } +
            AccessPoint("Far", "cc:00:00:00:00:01", 2412, -80, "")
        val r = WifiAnalysis.smartDevice(conn, aps)
        assertEquals(Band.GHZ_5, r.currentBand)
        assertEquals(true, r.sharedNameAcrossBands)
        assertEquals(6, r.ourChannel24)
        assertEquals(6, r.neighboursOnOurChannel)
        assertEquals(11, r.quietestChannel)
        assertEquals(0, r.quietestCount)
    }
}

class HistoryAndTelemetryTest {
    @Test fun scanHistoryRecordsNewDevicesAndFixes() {
        val router = Device("192.168.1.1", isGateway = true, services = setOf(Scanner.UPNP_IGD))
        val first = ScanOutcome(listOf(router), startedAt = 1000, durationMs = 10)
        val f1 = Checks.evaluate(first.devices, null).findings
        var s = ScanRepository.applyScan(AppState(), first, f1)
        assertTrue(s.history.isEmpty()) // the first scan is the baseline
        val newcomer = Device("192.168.1.50", mdnsHost = "mystery.local")
        val second = ScanOutcome(listOf(router.copy(services = emptySet()), newcomer), startedAt = 2000, durationMs = 10)
        s = ScanRepository.applyScan(s, second, Checks.evaluate(second.devices, null).findings)
        val kinds = s.history.map { it.kind }.toSet()
        assertEquals(setOf(HistoryKind.NEW_DEVICE, HistoryKind.ISSUE_FIXED), kinds)
        assertEquals("mystery", s.history.first { it.kind == HistoryKind.NEW_DEVICE }.subject)
    }

    @Test fun bucketsHideExactNumbers() {
        assertEquals("0", Telemetry.countBucket(0))
        assertEquals("6-15", Telemetry.countBucket(12))
        assertEquals("60+", Telemetry.countBucket(200))
        assertEquals("10-30s", Telemetry.durationBucket(21_000))
    }
}

class HealthTest {
    @Test fun scoreDropsWithSeverity() {
        assertEquals(100, Health.score(emptyList(), 0))
        val high = Finding(FindingType.TELNET_OPEN, "k")
        val low = Finding(FindingType.CAMERA_STREAM_OPEN, "k")
        assertEquals(79, Health.score(listOf(high, low), 0))
        assertEquals(90, Health.score(emptyList(), 20)) // unknown devices cost at most 10
        assertEquals(5, Health.score(List(10) { high }, 0))
        assertEquals(Health.Level.SECURE, Health.level(80))
        assertEquals(Health.Level.FAIR, Health.level(60))
        assertEquals(Health.Level.AT_RISK, Health.level(40))
    }

    @Test fun deviceThatDisappearsIsNotCountedAsFixed() {
        val cam = Device("192.168.1.9", upnpUuid = "cam", openPorts = setOf(23))
        val first = ScanOutcome(listOf(cam), startedAt = 1000, durationMs = 10)
        var s = ScanRepository.applyScan(AppState(), first, Checks.evaluate(first.devices, null).findings)
        val second = ScanOutcome(emptyList(), startedAt = 2000, durationMs = 10)
        s = ScanRepository.applyScan(s, second, Checks.evaluate(second.devices, null).findings)
        assertTrue(s.history.none { it.kind == HistoryKind.ISSUE_FIXED })
    }
}

class DeviceRiskTest {
    private val telnetCam = Device("192.168.1.9", upnpUuid = "cam", upnpName = "Hall Cam", openPorts = setOf(23, 554))

    @Test fun issuesAndUnknownRaiseRisk() {
        val f = Checks.evaluate(listOf(telnetCam), null).findings
        val r = DeviceRisk.assess(telnetCam, f, marked = false, isNew = true)
        assertEquals(DeviceRisk.Level.HIGH, r.level)
        assertTrue(DeviceRisk.Reason.HIGH_ISSUE in r.reasons)
        assertTrue(DeviceRisk.Reason.NEW_DEVICE in r.reasons)
        assertTrue(r.score <= 100)
    }

    @Test fun markedQuietDeviceIsLow() {
        val tv = Device("192.168.1.30", mdnsHost = "tv.local", services = setOf("_googlecast._tcp.local"))
        val r = DeviceRisk.assess(tv, emptyList(), marked = true, isNew = false)
        assertEquals(DeviceRisk.Level.LOW, r.level)
        assertEquals(0, DeviceRisk.assess(Device("1", isSelf = true), emptyList(), false, true).score)
    }

    @Test fun isolationAdviceFitsTheDevice() {
        val f = Checks.evaluate(listOf(telnetCam), null).findings
        val a = Isolation.advise(telnetCam, f, marked = false)
        assertTrue(Isolation.Advice.GUEST_NETWORK in a)
        assertTrue(Isolation.Advice.CLOSE_REMOTE_ACCESS in a)
        assertTrue(Isolation.Advice.CAMERA_CLOUD in a)
        assertEquals(Isolation.Advice.IDENTIFY_FIRST, a.first())
        assertTrue(Isolation.advise(Device("1", isSelf = true), emptyList(), true).isEmpty())
    }

    @Test fun newDevicesAndBlockedTracking() {
        val router = Device("192.168.1.1", isGateway = true)
        var s = ScanRepository.applyScan(AppState(), ScanOutcome(listOf(router), 1000, 10), emptyList())
        assertTrue(s.lastScan!!.newKeys.isEmpty()) // first scan is the baseline
        val stranger = Device("192.168.1.77", mdnsHost = "stranger.local")
        s = ScanRepository.applyScan(s, ScanOutcome(listOf(router, stranger), 2000, 10), emptyList())
        assertEquals(setOf(stranger.identityKey), s.lastScan!!.newKeys)
        s = s.copy(blocked = mapOf(stranger.identityKey to 2500L))
        assertTrue(s.blockedStillPresent().isEmpty()) // blocked after the last scan
        s = ScanRepository.applyScan(s, ScanOutcome(listOf(router, stranger), 3000, 10), emptyList())
        assertEquals(listOf(stranger), s.blockedStillPresent())
        assertTrue(s.lastScan!!.newKeys.isEmpty())
    }
}
