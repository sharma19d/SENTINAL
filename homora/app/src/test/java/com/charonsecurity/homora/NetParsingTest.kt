package com.charonsecurity.homora

import com.charonsecurity.homora.net.Discovery
import com.charonsecurity.homora.net.Dns
import com.charonsecurity.homora.net.Ipv4
import com.charonsecurity.homora.net.LanHttp
import com.charonsecurity.homora.net.NetBios
import com.charonsecurity.homora.net.Ssdp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream

class Ipv4Test {
    @Test fun parseAndFormatRoundTrip() {
        val ip = Ipv4.parse("192.168.1.20")!!
        assertEquals("192.168.1.20", Ipv4.format(ip))
        assertNull(Ipv4.parse("192.168.1"))
        assertNull(Ipv4.parse("192.168.1.256"))
        assertNull(Ipv4.parse("192.168.01.1"))
    }

    @Test fun privateRanges() {
        assertTrue(Ipv4.isPrivate(Ipv4.parse("10.0.0.5")!!))
        assertTrue(Ipv4.isPrivate(Ipv4.parse("172.20.1.1")!!))
        assertTrue(Ipv4.isPrivate(Ipv4.parse("192.168.0.1")!!))
        assertFalse(Ipv4.isPrivate(Ipv4.parse("172.32.0.1")!!))
        assertFalse(Ipv4.isPrivate(Ipv4.parse("8.8.8.8")!!))
    }

    @Test fun scanRangeIsTheOwnSlash24Only() {
        val self = Ipv4.parse("192.168.1.20")!!
        val hosts = Ipv4.scanRange(self, 24)
        assertEquals(253, hosts.size) // .1-.254 minus ourselves
        assertFalse(self in hosts)
        assertEquals("192.168.1.1", Ipv4.format(hosts.first()))
        assertEquals("192.168.1.254", Ipv4.format(hosts.last()))
        // A /16 network is still capped at the phone's /24.
        assertEquals(253, Ipv4.scanRange(Ipv4.parse("10.0.5.9")!!, 16).size)
        // Never a public network.
        assertTrue(Ipv4.scanRange(Ipv4.parse("100.64.3.2")!!, 24).isEmpty())
    }

    @Test fun reverseName() {
        assertEquals("20.1.168.192.in-addr.arpa", Ipv4.reverseName(Ipv4.parse("192.168.1.20")!!))
    }
}

class DnsTest {
    private fun name(out: ByteArrayOutputStream, n: String) {
        n.split('.').forEach { out.write(it.length); out.write(it.toByteArray()) }
        out.write(0)
    }
    private fun u16(out: ByteArrayOutputStream, v: Int) { out.write(v ushr 8); out.write(v and 255) }

    @Test fun queryEncodesQuestionAndQuBit() {
        val q = Dns.query(0x1234, "_googlecast._tcp.local", Dns.TYPE_PTR, unicastResponse = true)
        assertEquals(0x12, q[0].toInt() and 255)
        assertEquals(1, q[5].toInt()) // one question
        val tail = q.takeLast(4).map { it.toInt() and 255 }
        assertEquals(listOf(0, 12, 0x80, 1), tail)
    }

    @Test fun parsesCompressedPtrSrvTxtAndA() {
        val out = ByteArrayOutputStream()
        u16(out, 0); u16(out, 0x8400); u16(out, 0); u16(out, 4); u16(out, 0); u16(out, 0)
        // PTR _googlecast._tcp.local -> Living Room TV._googlecast._tcp.local
        val svcOffset = out.size()
        name(out, "_googlecast._tcp.local")
        u16(out, Dns.TYPE_PTR); u16(out, 1); u16(out, 0); u16(out, 120)
        val inst = ByteArrayOutputStream().apply { write(14); write("Living Room TV".toByteArray()); write(0xC0); write(svcOffset) }.toByteArray()
        u16(out, inst.size); out.write(inst)
        // SRV instance -> tv.local:8009 (name via pointer to the instance label above)
        val instOffset = svcOffset + "_googlecast._tcp.local".length + 2 + 10
        out.write(0xC0); out.write(instOffset)
        u16(out, Dns.TYPE_SRV); u16(out, 1); u16(out, 0); u16(out, 120)
        val srv = ByteArrayOutputStream().apply { u16(this, 0); u16(this, 0); u16(this, 8009); name(this, "tv.local") }.toByteArray()
        u16(out, srv.size); out.write(srv)
        // TXT fn=Living Room TV, md=Chromecast
        out.write(0xC0); out.write(instOffset)
        u16(out, Dns.TYPE_TXT); u16(out, 1); u16(out, 0); u16(out, 120)
        val txt = ByteArrayOutputStream().apply {
            listOf("fn=Living Room TV", "md=Chromecast").forEach { write(it.length); write(it.toByteArray()) }
        }.toByteArray()
        u16(out, txt.size); out.write(txt)
        // A tv.local -> 192.168.1.30
        name(out, "tv.local")
        u16(out, Dns.TYPE_A); u16(out, 0x8001); u16(out, 0); u16(out, 120); u16(out, 4)
        out.write(Ipv4.toBytes(Ipv4.parse("192.168.1.30")!!))

        val msg = Dns.parse(out.toByteArray())!!
        assertTrue(msg.isResponse)
        assertEquals(4, msg.records.size)
        assertEquals(Dns.Ptr("Living Room TV._googlecast._tcp.local"), msg.records[0].data)
        assertEquals(Dns.Srv(8009, "tv.local"), msg.records[1].data)
        assertEquals("Living Room TV._googlecast._tcp.local", msg.records[1].name)

        val src = Ipv4.parse("192.168.1.30")!!
        val info = Discovery.merge(Discovery.MdnsInfo(), src, msg)
        assertEquals("tv.local", info.host)
        assertEquals("Living Room TV", info.instance)
        assertEquals("Chromecast", info.model)
        assertTrue("_googlecast._tcp.local" in info.services)
    }

    @Test fun rejectsGarbageAndPointerLoops() {
        assertNull(Dns.parse(byteArrayOf(1, 2, 3)))
        val loop = byteArrayOf(0, 0, 0x84.toByte(), 0, 0, 0, 0, 1, 0, 0, 0, 0, 0xC0.toByte(), 12)
        assertNull(Dns.parse(loop))
    }

    @Test fun airplayNamesAreCleaned() {
        assertEquals("Kitchen", Discovery.cleanInstance("A1B2C3D4E5F6@Kitchen"))
        assertEquals("Office Printer", Discovery.cleanInstance("Office Printer"))
    }
}

class SsdpTest {
    @Test fun parsesResponseAndGateway() {
        val r = Ssdp.parseResponse(
            "HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=120\r\nLOCATION: http://192.168.1.1:1900/rootDesc.xml\r\n" +
                "SERVER: Linux UPnP/1.0 MiniUPnPd/2.1\r\nST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n" +
                "USN: uuid:ABCD-1234::urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n",
        )!!
        assertEquals("http://192.168.1.1:1900/rootDesc.xml", r.location)
        assertEquals("abcd-1234", r.uuid)
        assertTrue(r.isInternetGateway)
        assertNull(Ssdp.parseResponse("garbage"))
    }

    @Test fun parsesDescription() {
        val d = Ssdp.parseDescription(
            "<root><device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>" +
                "<friendlyName>Bedroom TV</friendlyName><manufacturer>Samsung Electronics</manufacturer>" +
                "<modelName>UE43 &amp; more</modelName></device></root>",
        )
        assertEquals("Bedroom TV", d.friendlyName)
        assertEquals("Samsung Electronics", d.manufacturer)
        assertEquals("UE43 & more", d.modelName)
        assertNull(d.modelNumber)
    }
}

class NetBiosTest {
    @Test fun requestIsWellFormed() {
        val r = NetBios.nodeStatusRequest(0x0102)
        assertEquals(50, r.size)
        assertEquals(32, r[12].toInt())
        assertEquals('C'.code, r[13].toInt()) // '*' = 0x2A -> 'C','K'
        assertEquals('K'.code, r[14].toInt())
        assertEquals(0x21, r[47].toInt())
    }

    @Test fun parsesWorkstationName() {
        val resp = ByteArray(57 + 18 * 2)
        resp[56] = 2
        fun entry(at: Int, name: String, suffix: Int, group: Boolean) {
            name.padEnd(15).toByteArray().copyInto(resp, at)
            resp[at + 15] = suffix.toByte()
            resp[at + 16] = if (group) 0x80.toByte() else 0
        }
        entry(57, "WORKGROUP", 0, true)
        entry(75, "DESKTOP-ABC", 0, false)
        assertEquals("DESKTOP-ABC", NetBios.parseNodeStatus(resp))
        assertNull(NetBios.parseNodeStatus(ByteArray(10)))
    }
}

class LanHttpTest {
    @Test fun parsesReplyAndTitle() {
        val r = LanHttp.parse("HTTP/1.1 200 OK\r\nServer: lighttpd\r\nContent-Type: text/html\r\n\r\n<html><head><title>  TP-Link  Archer C6 </title></head></html>")!!
        assertEquals(200, r.status)
        assertEquals("lighttpd", r.headers["server"])
        assertEquals("TP-Link Archer C6", LanHttp.title(r.body))
        assertNull(LanHttp.title("<title>Index</title>"))
        assertNull(LanHttp.parse("not http"))
    }
}
