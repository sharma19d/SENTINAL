package com.charonsecurity.homora.net

import java.net.ConnectException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NoRouteToHostException
import java.net.Socket
import java.net.SocketTimeoutException

/** Single-packet probes. Each one only asks a device a question; none of them logs in or sends a payload. */
object Probe {

    enum class PortState { OPEN, CLOSED, NO_ANSWER }

    /**
     * TCP connect to [port]. A refused connection still proves the host
     * exists (CLOSED), which is how devices are found without ARP access.
     */
    fun tcp(ip: Int, port: Int, timeoutMs: Int): PortState = try {
        Socket().use { it.connect(InetSocketAddress(InetAddress.getByAddress(Ipv4.toBytes(ip)), port), timeoutMs) }
        PortState.OPEN
    } catch (_: NoRouteToHostException) {
        PortState.NO_ANSWER
    } catch (e: ConnectException) {
        if (e.message?.contains("EHOSTUNREACH") == true) PortState.NO_ANSWER else PortState.CLOSED
    } catch (_: SocketTimeoutException) {
        PortState.NO_ANSWER
    } catch (_: Exception) {
        PortState.NO_ANSWER
    }

    /** One UDP request/response; returns the reply bytes or null. */
    fun udp(ip: Int, port: Int, payload: ByteArray, timeoutMs: Int): ByteArray? = try {
        DatagramSocket().use { s ->
            s.soTimeout = timeoutMs
            val addr = InetAddress.getByAddress(Ipv4.toBytes(ip))
            s.send(DatagramPacket(payload, payload.size, addr, port))
            val buf = ByteArray(2048)
            val p = DatagramPacket(buf, buf.size)
            s.receive(p)
            buf.copyOf(p.length)
        }
    } catch (_: Exception) {
        null
    }

    /** The name the router's DNS has for [ip] (often the DHCP hostname), or null. */
    fun reverseDns(dnsServer: Int, ip: Int, timeoutMs: Int = 800): String? {
        val id = (ip xor 0x5a5a) and 0xFFFF
        val reply = udp(dnsServer, 53, Dns.query(id, Ipv4.reverseName(ip), Dns.TYPE_PTR, recursionDesired = true), timeoutMs)
            ?: return null
        val msg = Dns.parse(reply) ?: return null
        if (msg.id != id || msg.rcode != 0) return null
        return msg.records.firstNotNullOfOrNull { (it.data as? Dns.Ptr)?.target }
            ?.takeIf { it.isNotBlank() && !it.endsWith("in-addr.arpa") }
    }

    /** Asks the device itself over unicast mDNS for its ".local" name (Apple, Linux, many IoT devices answer). */
    fun mdnsReverse(ip: Int, timeoutMs: Int = 800): String? {
        val id = (ip xor 0x3c3c) and 0xFFFF
        val reply = udp(ip, 5353, Dns.query(id, Ipv4.reverseName(ip), Dns.TYPE_PTR), timeoutMs) ?: return null
        return Dns.parse(reply)?.records?.firstNotNullOfOrNull { r -> (r.data as? Dns.Ptr)?.target?.takeIf { it.endsWith(".local") } }
    }

    fun netbiosName(ip: Int, timeoutMs: Int = 800): String? {
        val reply = udp(ip, NetBios.PORT, NetBios.nodeStatusRequest((ip and 0x7FFF) or 1), timeoutMs) ?: return null
        return NetBios.parseNodeStatus(reply)
    }

    /**
     * Round-trip time of a DNS query to the router, in ms, or null if it does
     * not answer DNS. Used as the fast-updating latency on the Wi-Fi meter.
     */
    fun dnsRoundTripMs(dnsServer: Int, timeoutMs: Int = 1000): Double? {
        val id = (System.nanoTime() and 0xFFFF).toInt()
        val q = Dns.query(id, "localhost", Dns.TYPE_A, recursionDesired = true)
        val start = System.nanoTime()
        val reply = udp(dnsServer, 53, q, timeoutMs) ?: return null
        val ms = (System.nanoTime() - start) / 1e6
        return if (Dns.parse(reply)?.id == id) ms else null
    }

    /** Fallback latency: time to complete (or be refused) a TCP connection to the router. */
    fun tcpRoundTripMs(ip: Int, port: Int, timeoutMs: Int = 1000): Double? {
        val start = System.nanoTime()
        val state = tcp(ip, port, timeoutMs)
        val ms = (System.nanoTime() - start) / 1e6
        return if (state == PortState.NO_ANSWER) null else ms
    }
}
