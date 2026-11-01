package com.charonsecurity.homora.net

import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException

/**
 * A tiny HTTP/1.0 GET over a raw socket, for reading a LAN device's own web
 * page or UPnP description. Never used for anything off the local network.
 */
object LanHttp {
    data class Reply(val status: Int, val headers: Map<String, String>, val body: String)

    fun get(ip: Int, port: Int, path: String = "/", timeoutMs: Int = 1500, maxBytes: Int = 32 * 1024): Reply? {
        require(Ipv4.isPrivate(ip)) { "LAN only" }
        val host = Ipv4.format(ip)
        return try {
            Socket().use { s ->
                s.connect(InetSocketAddress(host, port), timeoutMs)
                s.soTimeout = timeoutMs
                val req = "GET $path HTTP/1.0\r\nHost: $host:$port\r\nUser-Agent: Homora\r\nAccept: */*\r\nConnection: close\r\n\r\n"
                s.getOutputStream().apply { write(req.toByteArray(Charsets.US_ASCII)); flush() }
                val input = s.getInputStream()
                val out = ByteArrayOutputStream()
                val chunk = ByteArray(4096)
                val deadline = System.currentTimeMillis() + timeoutMs * 2
                try {
                    while (out.size() < maxBytes && System.currentTimeMillis() < deadline) {
                        val n = input.read(chunk)
                        if (n < 0) break
                        out.write(chunk, 0, n)
                    }
                } catch (_: SocketTimeoutException) {
                    // keep what arrived
                }
                parse(out.toString(Charsets.ISO_8859_1.name()))
            }
        } catch (_: Exception) {
            null
        }
    }

    fun parse(raw: String): Reply? {
        val split = raw.indexOf("\r\n\r\n").takeIf { it >= 0 } ?: raw.indexOf("\n\n").takeIf { it >= 0 } ?: return null
        val head = raw.substring(0, split).split("\r\n", "\n")
        val status = head.firstOrNull()?.split(' ')?.getOrNull(1)?.toIntOrNull() ?: return null
        val headers = head.drop(1).mapNotNull { line ->
            val i = line.indexOf(':')
            if (i > 0) line.substring(0, i).trim().lowercase() to line.substring(i + 1).trim() else null
        }.toMap()
        return Reply(status, headers, raw.substring(split).trimStart())
    }

    /** The page's <title>, cleaned up, if it says something useful. */
    fun title(body: String): String? =
        Regex("<title[^>]*>([^<]{1,120})</title>", RegexOption.IGNORE_CASE).find(body)?.groupValues?.get(1)
            ?.replace(Regex("\\s+"), " ")?.trim()?.takeIf { it.isNotEmpty() && !it.equals("index", true) }
}
