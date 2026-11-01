package com.charonsecurity.homora.net

/** NetBIOS node-status query (RFC 1002 §4.2.17), which returns a Windows/Samba machine's name. */
object NetBios {
    const val PORT = 137

    fun nodeStatusRequest(id: Int): ByteArray {
        val name = ByteArray(32)
        // The wildcard name "*" padded with NULs, first-level encoded: each nibble + 'A'.
        val raw = ByteArray(16).also { it[0] = '*'.code.toByte() }
        for (i in 0 until 16) {
            val b = raw[i].toInt() and 255
            name[2 * i] = ('A'.code + (b ushr 4)).toByte()
            name[2 * i + 1] = ('A'.code + (b and 15)).toByte()
        }
        return byteArrayOf(
            (id ushr 8).toByte(), id.toByte(), 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 32,
        ) + name + byteArrayOf(0, 0, 0x21, 0, 1)
    }

    /** The machine's unique workstation name (suffix 0x00, not a group), or null. */
    fun parseNodeStatus(buf: ByteArray, length: Int = buf.size): String? {
        // header (12) + name (34) + type/class/ttl (8) + rdlength (2) = 56
        if (length < 57) return null
        val count = buf[56].toInt() and 255
        var p = 57
        repeat(count) {
            if (p + 18 > length) return null
            val name = String(buf, p, 15, Charsets.US_ASCII).trimEnd(' ', '\u0000')
            val suffix = buf[p + 15].toInt() and 255
            val flags = ((buf[p + 16].toInt() and 255) shl 8) or (buf[p + 17].toInt() and 255)
            val isGroup = flags and 0x8000 != 0
            if (suffix == 0 && !isGroup && name.isNotBlank()) return name
            p += 18
        }
        return null
    }
}
