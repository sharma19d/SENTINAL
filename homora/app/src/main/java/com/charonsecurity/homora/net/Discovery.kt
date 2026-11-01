package com.charonsecurity.homora.net

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException

/**
 * Listens for devices that announce themselves (mDNS/Bonjour and UPnP/SSDP).
 * Queries go out from an ordinary UDP port, so responders reply to us
 * directly (RFC 6762 §6.7 "legacy unicast"; SSDP replies are unicast too) and
 * no multicast lock or port 5353 binding is needed.
 */
class Discovery(private val bindToWifi: (DatagramSocket) -> Unit = {}) {

    data class MdnsInfo(
        val host: String? = null,
        val instance: String? = null,
        val model: String? = null,
        val services: Set<String> = emptySet(),
    )

    data class SsdpInfo(val responses: List<Ssdp.Response>)

    fun mdns(windowMs: Long = 3000): Map<Int, MdnsInfo> {
        val found = HashMap<Int, MdnsInfo>()
        val askedTypes = HashSet<String>(COMMON_SERVICES)
        try {
            DatagramSocket().use { s ->
                bindToWifi(s)
                val group = InetAddress.getByName("224.0.0.251")
                fun send(types: Collection<String>) {
                    types.chunked(12).forEachIndexed { i, chunk ->
                        val q = Dns.query(0x4d00 + i, chunk.map { Dns.Question(it, Dns.TYPE_PTR) })
                        s.send(DatagramPacket(q, q.size, group, 5353))
                    }
                }
                send(listOf(SERVICES_META) + COMMON_SERVICES)
                val buf = ByteArray(9000)
                val deadline = System.currentTimeMillis() + windowMs
                var followUpSent = false
                while (true) {
                    val left = deadline - System.currentTimeMillis()
                    if (left <= 0) break
                    if (!followUpSent && left < windowMs / 2) {
                        // Second round: ask for instances of service types devices told us about.
                        val extra = found.values.flatMap { it.services }.filter { askedTypes.add(it) }
                        if (extra.isNotEmpty()) send(extra)
                        followUpSent = true
                    }
                    s.soTimeout = left.toInt().coerceAtLeast(1)
                    val p = DatagramPacket(buf, buf.size)
                    try {
                        s.receive(p)
                    } catch (_: SocketTimeoutException) {
                        break
                    }
                    val src = Ipv4.fromBytes(p.address.address) ?: continue
                    if (!Ipv4.isPrivate(src)) continue
                    val msg = Dns.parse(buf, p.length) ?: continue
                    found[src] = merge(found[src] ?: MdnsInfo(), src, msg)
                }
            }
        } catch (_: Exception) {
            // Discovery is best effort; the TCP sweep still finds devices.
        }
        return found
    }

    fun ssdp(windowMs: Long = 3000): Map<Int, SsdpInfo> {
        val found = HashMap<Int, MutableList<Ssdp.Response>>()
        try {
            DatagramSocket().use { s ->
                bindToWifi(s)
                val group = InetAddress.getByName(Ssdp.ADDRESS)
                for (target in listOf("ssdp:all", "urn:schemas-upnp-org:device:InternetGatewayDevice:1")) {
                    val m = Ssdp.mSearch(target)
                    s.send(DatagramPacket(m, m.size, group, Ssdp.PORT))
                }
                val buf = ByteArray(4096)
                val deadline = System.currentTimeMillis() + windowMs
                while (true) {
                    val left = deadline - System.currentTimeMillis()
                    if (left <= 0) break
                    s.soTimeout = left.toInt().coerceAtLeast(1)
                    val p = DatagramPacket(buf, buf.size)
                    try {
                        s.receive(p)
                    } catch (_: SocketTimeoutException) {
                        break
                    }
                    val src = Ipv4.fromBytes(p.address.address) ?: continue
                    if (!Ipv4.isPrivate(src)) continue
                    val r = Ssdp.parseResponse(String(buf, 0, p.length, Charsets.UTF_8)) ?: continue
                    found.getOrPut(src) { ArrayList() } += r
                }
            }
        } catch (_: Exception) {
        }
        return found.mapValues { SsdpInfo(it.value.distinct()) }
    }

    companion object {
        private const val SERVICES_META = "_services._dns-sd._udp.local"

        val COMMON_SERVICES = listOf(
            "_googlecast._tcp.local", "_airplay._tcp.local", "_raop._tcp.local", "_spotify-connect._tcp.local",
            "_ipp._tcp.local", "_printer._tcp.local", "_pdl-datastream._tcp.local", "_hap._tcp.local",
            "_companion-link._tcp.local", "_device-info._tcp.local", "_smb._tcp.local", "_workstation._tcp.local",
            "_http._tcp.local", "_amzn-wplay._tcp.local", "_androidtvremote2._tcp.local", "_matter._tcp.local",
            "_sonos._tcp.local", "_esphomelib._tcp.local", "_hue._tcp.local", "_ssh._tcp.local",
            "_rfb._tcp.local", "_miio._udp.local", "_shelly._tcp.local", "_afpovertcp._tcp.local",
        )

        private val TXT_NAME_KEYS = listOf("fn", "n", "name", "friendlyname")
        private val TXT_MODEL_KEYS = listOf("md", "model", "am", "ty", "product", "usb_mdl")

        internal fun merge(prev: MdnsInfo, src: Int, msg: Dns.Message): MdnsInfo {
            var host = prev.host
            var instance = prev.instance
            var model = prev.model
            val services = prev.services.toMutableSet()
            for (r in msg.records) {
                when (val d = r.data) {
                    is Dns.A -> if (d.ip == src && r.name.endsWith(".local")) host = host ?: r.name
                    is Dns.Ptr -> when {
                        r.name == SERVICES_META -> services += d.target
                        r.name.startsWith("_") && d.target.endsWith(r.name) -> {
                            services += r.name
                            instance = instance ?: cleanInstance(d.target.removeSuffix("." + r.name))
                        }
                    }
                    is Dns.Srv -> host = host ?: d.target.takeIf { it.endsWith(".local") }
                    is Dns.Txt -> {
                        val kv = d.entries.mapNotNull { e ->
                            val i = e.indexOf('=')
                            if (i > 0) e.substring(0, i).lowercase() to e.substring(i + 1) else null
                        }.toMap()
                        TXT_NAME_KEYS.firstNotNullOfOrNull { kv[it]?.takeIf(String::isNotBlank) }?.let { instance = it }
                        if (model == null) model = TXT_MODEL_KEYS.firstNotNullOfOrNull { kv[it]?.takeIf(String::isNotBlank) }
                    }
                    Dns.Other -> {}
                }
            }
            return MdnsInfo(host, instance, model, services)
        }

        /** AirPlay audio names look like "A1B2C3D4E5F6@Kitchen"; keep the readable part. */
        internal fun cleanInstance(name: String): String? =
            name.substringAfter('@').replace("\\032", " ").trim().takeIf { it.isNotEmpty() }
    }
}
