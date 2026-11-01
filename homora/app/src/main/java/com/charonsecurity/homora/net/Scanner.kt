package com.charonsecurity.homora.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.net.DatagramSocket
import java.util.concurrent.atomic.AtomicInteger

/** The phone's view of the Wi-Fi network it is on. */
data class LanInfo(val selfIp: Int, val prefixLength: Int, val gateway: Int?, val dnsServers: List<Int>)

data class ScanOutcome(val devices: List<Device>, val startedAt: Long, val durationMs: Long)

/**
 * Finds the devices on the phone's own Wi-Fi network. Scope is fixed: the
 * private /24 the phone is on, a short list of ports, and read-only questions.
 * It never tries a password, sends an exploit, or touches another network.
 */
class Scanner(private val bindToWifi: (DatagramSocket) -> Unit = {}) {

    enum class Phase { DISCOVERING, CHECKING_DEVICES, DONE }
    data class Progress(val phase: Phase, val fraction: Float, val devicesFound: Int)

    suspend fun scan(lan: LanInfo, onProgress: (Progress) -> Unit = {}): ScanOutcome = coroutineScope {
        val started = System.currentTimeMillis()
        val hosts = Ipv4.scanRange(lan.selfIp, lan.prefixLength)
        require(hosts.isNotEmpty()) { "not a private network" }
        val discovery = Discovery(bindToWifi)
        val io = Dispatchers.IO.limitedParallelism(SWEEP_PARALLELISM)

        val mdnsJob = async(Dispatchers.IO) { discovery.mdns() }
        val ssdpJob = async(Dispatchers.IO) { discovery.ssdp() }

        // 1. Sweep: a host is alive if any port answers, even with "refused".
        val done = AtomicInteger()
        val alive = AtomicInteger()
        val sweep = hosts.map { ip ->
            async(io) {
                var firstOpen: Int? = null
                var isAlive = false
                for (port in SWEEP_PORTS) {
                    ensureActive()
                    when (Probe.tcp(ip, port, SWEEP_TIMEOUT_MS)) {
                        Probe.PortState.OPEN -> { firstOpen = port; isAlive = true }
                        Probe.PortState.CLOSED -> isAlive = true
                        Probe.PortState.NO_ANSWER -> {}
                    }
                    if (isAlive) break
                }
                if (isAlive) alive.incrementAndGet()
                onProgress(Progress(Phase.DISCOVERING, 0.7f * done.incrementAndGet() / hosts.size, alive.get()))
                if (isAlive) ip to firstOpen else null
            }
        }.awaitAll().filterNotNull().toMap()

        val mdns = mdnsJob.await()
        val ssdp = ssdpJob.await()
        val candidates = (sweep.keys + mdns.keys + ssdp.keys + listOfNotNull(lan.gateway))
            .filter { it in hosts }.toSortedSet()

        // 2. Details for each device found.
        val detailGate = Semaphore(DETAIL_PARALLELISM)
        val detailed = AtomicInteger()
        val dns = lan.gateway ?: lan.dnsServers.firstOrNull { Ipv4.isPrivate(it) }
        val devices = candidates.map { ip ->
            async(Dispatchers.IO) {
                detailGate.withPermit {
                    val d = describe(ip, lan, sweep[ip], mdns[ip], ssdp[ip], dns)
                    onProgress(Progress(Phase.CHECKING_DEVICES, 0.7f + 0.3f * detailed.incrementAndGet() / candidates.size, candidates.size))
                    d
                }
            }
        }.awaitAll()

        val self = Device(ip = Ipv4.format(lan.selfIp), isSelf = true)
        onProgress(Progress(Phase.DONE, 1f, devices.size + 1))
        ScanOutcome(listOf(self) + devices, started, System.currentTimeMillis() - started)
    }

    private suspend fun describe(
        ip: Int, lan: LanInfo, firstOpen: Int?, m: Discovery.MdnsInfo?, s: Discovery.SsdpInfo?, dnsServer: Int?,
    ): Device = withContext(Dispatchers.IO) {
        val open = DETAIL_PORTS.filter { it == firstOpen || Probe.tcp(ip, it, DETAIL_TIMEOUT_MS) == Probe.PortState.OPEN }.toSet()
        val netbios = Probe.netbiosName(ip)
        val mdnsHost = m?.host ?: Probe.mdnsReverse(ip)
        val dnsName = dnsServer?.let { Probe.reverseDns(it, ip) }
        val http = when {
            80 in open -> LanHttp.get(ip, 80)
            8080 in open -> LanHttp.get(ip, 8080)
            else -> null
        }
        val upnp = s?.responses?.firstNotNullOfOrNull { r ->
            r.location?.let { loc -> fetchDescription(ip, loc) }
        }
        Device(
            ip = Ipv4.format(ip),
            upnpUuid = s?.responses?.firstNotNullOfOrNull { it.uuid },
            upnpName = upnp?.friendlyName,
            manufacturer = upnp?.manufacturer,
            model = upnp?.modelName ?: m?.model,
            mdnsHost = mdnsHost,
            mdnsInstance = m?.instance,
            netbiosName = netbios,
            dnsName = dnsName,
            httpTitle = http?.body?.let(LanHttp::title),
            httpServer = http?.headers?.get("server")?.take(80),
            services = m?.services.orEmpty() + (if (s?.responses?.any { it.isInternetGateway } == true) setOf(UPNP_IGD) else emptySet()),
            openPorts = open,
            isGateway = ip == lan.gateway,
        )
    }

    /** Fetches a UPnP description, only from the device that announced it. */
    private fun fetchDescription(ip: Int, location: String): Ssdp.Description? {
        val m = Regex("^http://([0-9.]+):(\\d+)(/[^\\s]*)?$").find(location.trim()) ?: return null
        if (Ipv4.parse(m.groupValues[1]) != ip) return null
        val port = m.groupValues[2].toIntOrNull() ?: return null
        val reply = LanHttp.get(ip, port, m.groupValues[3].ifEmpty { "/" }) ?: return null
        return if (reply.status == 200) Ssdp.parseDescription(reply.body) else null
    }

    companion object {
        /** Marker service for a device advertising UPnP port forwarding. */
        const val UPNP_IGD = "upnp:igd"

        /** Ports that make most devices answer; a refusal counts as an answer. */
        val SWEEP_PORTS = listOf(80, 443, 22, 445, 62078, 8080, 554, 7000, 8008, 9100, 5000, 23, 139, 49152)

        /** Ports the security checks and device guesses look at. */
        val DETAIL_PORTS = listOf(21, 22, 23, 80, 139, 443, 445, 554, 1883, 2323, 3389, 5000, 5900, 7000, 8008, 8009, 8080, 8443, 9100, 49152, 62078)

        private const val SWEEP_PARALLELISM = 64
        private const val DETAIL_PARALLELISM = 12
        private const val SWEEP_TIMEOUT_MS = 400
        private const val DETAIL_TIMEOUT_MS = 600
    }
}
