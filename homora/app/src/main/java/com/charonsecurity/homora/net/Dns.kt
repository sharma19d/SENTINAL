package com.charonsecurity.homora.net

import java.io.ByteArrayOutputStream

/**
 * Minimal DNS wire format (RFC 1035), enough for mDNS service discovery,
 * reverse lookups and timing a query to the router. Only the record types the
 * app reads are decoded; everything else is skipped.
 */
object Dns {
    const val TYPE_A = 1
    const val TYPE_PTR = 12
    const val TYPE_TXT = 16
    const val TYPE_SRV = 33
    const val TYPE_ANY = 255
    private const val CLASS_IN = 1

    sealed interface Data
    data class Ptr(val target: String) : Data
    data class A(val ip: Int) : Data
    data class Srv(val port: Int, val target: String) : Data
    data class Txt(val entries: List<String>) : Data
    data object Other : Data

    data class Record(val name: String, val type: Int, val data: Data)
    data class Message(val id: Int, val isResponse: Boolean, val rcode: Int, val records: List<Record>)

    data class Question(val name: String, val type: Int)

    /**
     * A query for [questions]. [unicastResponse] sets the mDNS "QU" bit
     * (RFC 6762 §5.4), asking responders to answer us directly.
     */
    fun query(id: Int, questions: List<Question>, recursionDesired: Boolean = false, unicastResponse: Boolean = false): ByteArray {
        val out = ByteArrayOutputStream()
        out.u16(id)
        out.u16(if (recursionDesired) 0x0100 else 0)
        out.u16(questions.size)
        out.u16(0); out.u16(0); out.u16(0)
        for (q in questions) {
            writeName(out, q.name)
            out.u16(q.type)
            out.u16(if (unicastResponse) CLASS_IN or 0x8000 else CLASS_IN)
        }
        return out.toByteArray()
    }

    fun query(id: Int, name: String, type: Int, recursionDesired: Boolean = false, unicastResponse: Boolean = false) =
        query(id, listOf(Question(name, type)), recursionDesired, unicastResponse)

    /** Parses a message; returns null if it is malformed. Answer, authority and additional records are merged. */
    fun parse(buf: ByteArray, length: Int = buf.size): Message? = try {
        val r = Reader(buf, length)
        val id = r.u16()
        val flags = r.u16()
        val qd = r.u16(); val an = r.u16(); val ns = r.u16(); val ar = r.u16()
        repeat(qd) { r.name(); r.skip(4) }
        val records = ArrayList<Record>(an + ns + ar)
        repeat(an + ns + ar) {
            val name = r.name()
            val type = r.u16()
            r.skip(2) // class (+ mDNS cache-flush bit)
            r.skip(4) // ttl
            val len = r.u16()
            val start = r.pos
            val data: Data = when (type) {
                TYPE_A -> if (len == 4) A(Ipv4.fromBytes(buf.copyOfRange(start, start + 4))!!) else Other
                TYPE_PTR -> Ptr(r.name())
                TYPE_SRV -> { r.skip(4); val port = r.u16(); Srv(port, r.name()) }
                TYPE_TXT -> Txt(r.txt(start + len))
                else -> Other
            }
            r.pos = start + len
            if (r.pos > length) throw IndexOutOfBoundsException()
            records += Record(name, type, data)
        }
        Message(id, flags and 0x8000 != 0, flags and 0xF, records)
    } catch (_: RuntimeException) {
        null
    }

    private fun writeName(out: ByteArrayOutputStream, name: String) {
        for (label in name.trimEnd('.').split('.')) {
            if (label.isEmpty()) continue
            val bytes = label.toByteArray(Charsets.UTF_8)
            require(bytes.size <= 63) { "label too long" }
            out.write(bytes.size)
            out.write(bytes)
        }
        out.write(0)
    }

    private fun ByteArrayOutputStream.u16(v: Int) {
        write((v ushr 8) and 255); write(v and 255)
    }

    private class Reader(val buf: ByteArray, val length: Int) {
        var pos = 0
        fun u8(): Int {
            if (pos >= length) throw IndexOutOfBoundsException()
            return buf[pos++].toInt() and 255
        }
        fun u16(): Int = (u8() shl 8) or u8()
        fun skip(n: Int) {
            pos += n
            if (pos > length) throw IndexOutOfBoundsException()
        }

        /** A possibly compressed name; pointer loops are cut off. */
        fun name(): String {
            val labels = ArrayList<String>()
            var p = pos
            var jumped = false
            var hops = 0
            while (true) {
                if (p >= length) throw IndexOutOfBoundsException()
                val len = buf[p].toInt() and 255
                when {
                    len == 0 -> { p++; break }
                    len and 0xC0 == 0xC0 -> {
                        if (p + 1 >= length || ++hops > 32) throw IndexOutOfBoundsException()
                        val target = ((len and 0x3F) shl 8) or (buf[p + 1].toInt() and 255)
                        if (!jumped) pos = p + 2
                        jumped = true
                        p = target
                    }
                    else -> {
                        if (p + 1 + len > length) throw IndexOutOfBoundsException()
                        labels += String(buf, p + 1, len, Charsets.UTF_8)
                        p += 1 + len
                    }
                }
            }
            if (!jumped) pos = p
            return labels.joinToString(".")
        }

        fun txt(end: Int): List<String> {
            val out = ArrayList<String>()
            while (pos < end) {
                val len = u8()
                if (pos + len > end) throw IndexOutOfBoundsException()
                out += String(buf, pos, len, Charsets.UTF_8)
                pos += len
            }
            return out
        }
    }
}
