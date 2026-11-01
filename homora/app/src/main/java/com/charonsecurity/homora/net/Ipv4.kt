package com.charonsecurity.homora.net

/** IPv4 helpers. Addresses are held as Ints (network byte order, unsigned). */
object Ipv4 {

    fun parse(text: String): Int? {
        val parts = text.trim().split('.')
        if (parts.size != 4) return null
        var value = 0
        for (p in parts) {
            val octet = p.toIntOrNull() ?: return null
            if (octet !in 0..255 || (p.length > 1 && p.startsWith('0'))) return null
            value = (value shl 8) or octet
        }
        return value
    }

    fun format(ip: Int): String =
        "${(ip ushr 24) and 255}.${(ip ushr 16) and 255}.${(ip ushr 8) and 255}.${ip and 255}"

    fun fromBytes(b: ByteArray): Int? {
        if (b.size != 4) return null
        return ((b[0].toInt() and 255) shl 24) or ((b[1].toInt() and 255) shl 16) or
            ((b[2].toInt() and 255) shl 8) or (b[3].toInt() and 255)
    }

    fun toBytes(ip: Int): ByteArray = byteArrayOf(
        (ip ushr 24).toByte(), (ip ushr 16).toByte(), (ip ushr 8).toByte(), ip.toByte(),
    )

    /** RFC 1918 private ranges. The scanner refuses anything else. */
    fun isPrivate(ip: Int): Boolean {
        val a = (ip ushr 24) and 255
        val b = (ip ushr 16) and 255
        return a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)
    }

    /** "d.c.b.a.in-addr.arpa" for a reverse (PTR) lookup. */
    fun reverseName(ip: Int): String =
        "${ip and 255}.${(ip ushr 8) and 255}.${(ip ushr 16) and 255}.${(ip ushr 24) and 255}.in-addr.arpa"

    /**
     * The hosts to scan for a phone at [self] on a network of [prefixLength].
     * Never more than the /24 around the phone, so a large or misconfigured
     * network can't turn a home scan into a sweep of thousands of addresses.
     * Returns an empty list unless the network is private.
     */
    fun scanRange(self: Int, prefixLength: Int): List<Int> {
        if (!isPrivate(self)) return emptyList()
        val prefix = prefixLength.coerceIn(24, 30)
        val mask = if (prefix == 0) 0 else -1 shl (32 - prefix)
        val network = self and mask
        val broadcast = network or mask.inv()
        return ((network + 1) until broadcast).filter { it != self }
    }
}
