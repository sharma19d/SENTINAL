"""
SENTINEL Layer 1 — Metadata Extractor

Extracts application-layer metadata from raw packets:
  • DNS queries and responses
  • TLS Server Name Indication (SNI) from Client Hello
  • HTTP method, URI, Host, User-Agent
  • ARP requests and replies
  • mDNS service advertisements
  • SSDP/UPnP discovery messages
  • DHCP hostname and vendor class
"""

from __future__ import annotations
import struct
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


def extract_dns(packet) -> dict:
    """Extract DNS query/response metadata from a Scapy packet."""
    result = {"query_name": None, "query_type": None, "answers": [], "is_response": False}
    try:
        from scapy.layers.dns import DNS, DNSQR, DNSRR
        if not packet.haslayer(DNS):
            return result
        dns = packet[DNS]
        if dns.haslayer(DNSQR):
            qr = dns[DNSQR]
            qname = qr.qname
            if isinstance(qname, bytes):
                qname = qname.decode("utf-8", errors="ignore").rstrip(".")
            result["query_name"] = qname
            _type_map = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR",
                         15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 255: "ANY"}
            result["query_type"] = _type_map.get(qr.qtype, f"TYPE{qr.qtype}")
        if dns.qr == 1:
            result["is_response"] = True
            if dns.ancount and dns.ancount > 0:
                answers = []
                rr = dns.an
                for _ in range(dns.ancount):
                    if rr is None:
                        break
                    if hasattr(rr, "rdata"):
                        rdata = rr.rdata
                        if isinstance(rdata, bytes):
                            rdata = rdata.decode("utf-8", errors="ignore")
                        answers.append(str(rdata).rstrip("."))
                    rr = rr.payload if hasattr(rr, "payload") else None
                    if rr and not hasattr(rr, "rdata"):
                        break
                result["answers"] = answers
    except Exception as e:
        logger.debug("dns_extraction_error", error=str(e))
    return result


def extract_tls_sni(packet) -> dict:
    """Extract TLS SNI from Client Hello message."""
    result = {"sni": None, "tls_version": None}
    try:
        from scapy.layers.inet import TCP
        if not packet.haslayer(TCP):
            return result
        payload = bytes(packet[TCP].payload)
        if len(payload) < 6 or payload[0] != 0x16:
            return result
        tls_major, tls_minor = payload[1], payload[2]
        _versions = {(3,0): "SSL 3.0", (3,1): "TLS 1.0", (3,2): "TLS 1.1",
                     (3,3): "TLS 1.2", (3,4): "TLS 1.3"}
        result["tls_version"] = _versions.get((tls_major, tls_minor),
                                               f"TLS {tls_major}.{tls_minor}")
        if payload[5] != 0x01:
            return result
        sni = _parse_client_hello_sni(payload[5:])
        if sni:
            result["sni"] = sni
    except Exception as e:
        logger.debug("tls_sni_extraction_error", error=str(e))
    return result


def _parse_client_hello_sni(data: bytes) -> Optional[str]:
    """Parse TLS Client Hello handshake to extract SNI hostname."""
    try:
        pos = 4   # skip handshake header (type + 3-byte length)
        pos += 34  # client version (2) + random (32)
        if pos >= len(data):
            return None
        session_id_len = data[pos]
        pos += 1 + session_id_len
        if pos + 2 > len(data):
            return None
        cipher_suites_len = struct.unpack("!H", data[pos:pos + 2])[0]
        pos += 2 + cipher_suites_len
        if pos >= len(data):
            return None
        comp_methods_len = data[pos]
        pos += 1 + comp_methods_len
        if pos + 2 > len(data):
            return None
        extensions_len = struct.unpack("!H", data[pos:pos + 2])[0]
        pos += 2
        extensions_end = pos + extensions_len
        while pos + 4 <= extensions_end and pos + 4 <= len(data):
            ext_type = struct.unpack("!H", data[pos:pos + 2])[0]
            ext_len = struct.unpack("!H", data[pos + 2:pos + 4])[0]
            pos += 4
            if ext_type == 0x0000:  # SNI extension
                if pos + 5 <= len(data):
                    sni_type = data[pos + 2]
                    sni_len = struct.unpack("!H", data[pos + 3:pos + 5])[0]
                    if sni_type == 0 and pos + 5 + sni_len <= len(data):
                        return data[pos + 5:pos + 5 + sni_len].decode("ascii", errors="ignore")
                break
            pos += ext_len
    except (struct.error, IndexError):
        pass
    return None


def extract_http(packet) -> dict:
    """Extract HTTP request metadata from TCP payload."""
    result = {"method": None, "uri": None, "host": None,
              "user_agent": None, "content_type": None}
    try:
        from scapy.layers.inet import TCP
        if not packet.haslayer(TCP):
            return result
        payload = bytes(packet[TCP].payload)
        if len(payload) < 16:
            return result
        text = payload.decode("utf-8", errors="ignore")
        methods = ("GET ", "POST ", "PUT ", "DELETE ", "HEAD ",
                   "OPTIONS ", "PATCH ", "CONNECT ", "TRACE ")
        if not any(text.startswith(m) for m in methods):
            return result
        lines = text.split("\r\n")
        if not lines:
            return result
        parts = lines[0].split(" ")
        if len(parts) >= 2:
            result["method"] = parts[0]
            result["uri"] = parts[1]
        for line in lines[1:]:
            if not line:
                break
            lower = line.lower()
            if lower.startswith("host:"):
                result["host"] = line.split(":", 1)[1].strip()
            elif lower.startswith("user-agent:"):
                result["user_agent"] = line.split(":", 1)[1].strip()
            elif lower.startswith("content-type:"):
                result["content_type"] = line.split(":", 1)[1].strip()
    except Exception as e:
        logger.debug("http_extraction_error", error=str(e))
    return result


def extract_arp(packet) -> dict:
    """Extract ARP request/reply metadata."""
    result = {"operation": None, "sender_mac": None, "sender_ip": None,
              "target_mac": None, "target_ip": None}
    try:
        from scapy.layers.l2 import ARP
        if not packet.haslayer(ARP):
            return result
        arp = packet[ARP]
        result["operation"] = "request" if arp.op == 1 else "reply"
        result["sender_mac"] = arp.hwsrc
        result["sender_ip"] = arp.psrc
        result["target_mac"] = arp.hwdst
        result["target_ip"] = arp.pdst
    except Exception as e:
        logger.debug("arp_extraction_error", error=str(e))
    return result


def extract_mdns(packet) -> dict:
    """Extract mDNS (Multicast DNS) service advertisement metadata."""
    result = {"hostname": None, "service_type": None, "service_name": None, "records": []}
    try:
        from scapy.layers.dns import DNS, DNSQR
        from scapy.layers.inet import UDP
        if not packet.haslayer(UDP) or not packet.haslayer(DNS):
            return result
        udp = packet[UDP]
        if udp.dport != 5353 and udp.sport != 5353:
            return result
        dns = packet[DNS]
        records = []
        # Query records
        if dns.qdcount and dns.qdcount > 0:
            qr = dns.qd
            for _ in range(dns.qdcount):
                if qr is None:
                    break
                if hasattr(qr, "qname"):
                    name = qr.qname
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="ignore")
                    records.append(name.rstrip("."))
                qr = qr.payload if hasattr(qr, "payload") else None
                if qr and not hasattr(qr, "qname"):
                    break
        # Answer records
        for attr, count_attr in [("an", "ancount"), ("ns", "nscount"), ("ar", "arcount")]:
            count = getattr(dns, count_attr, 0)
            if not count:
                continue
            rr = getattr(dns, attr, None)
            for _ in range(count):
                if rr is None:
                    break
                if hasattr(rr, "rrname"):
                    name = rr.rrname
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="ignore")
                    records.append(name.rstrip("."))
                rr = rr.payload if hasattr(rr, "payload") else None
                if rr and not hasattr(rr, "rrname"):
                    break
        result["records"] = list(set(records))
        for record in records:
            if record.endswith(".local"):
                if "._tcp.local" in record or "._udp.local" in record:
                    result["service_type"] = record
                    parts = record.split(".")
                    if len(parts) > 3:
                        result["service_name"] = parts[0]
                else:
                    result["hostname"] = record
    except Exception as e:
        logger.debug("mdns_extraction_error", error=str(e))
    return result


def extract_ssdp(packet) -> dict:
    """Extract SSDP/UPnP discovery metadata (UDP port 1900)."""
    result = {"method": None, "location": None, "server": None,
              "usn": None, "service_type": None}
    try:
        from scapy.layers.inet import UDP
        if not packet.haslayer(UDP):
            return result
        udp = packet[UDP]
        if udp.dport != 1900 and udp.sport != 1900:
            return result
        payload = bytes(udp.payload)
        if len(payload) < 10:
            return result
        text = payload.decode("utf-8", errors="ignore")
        lines = text.split("\r\n")
        if not lines:
            return result
        result["method"] = lines[0].strip()
        for line in lines[1:]:
            if not line:
                continue
            lower = line.lower()
            if lower.startswith("location:"):
                result["location"] = line.split(":", 1)[1].strip()
            elif lower.startswith("server:"):
                result["server"] = line.split(":", 1)[1].strip()
            elif lower.startswith("usn:"):
                result["usn"] = line.split(":", 1)[1].strip()
            elif lower.startswith("st:") or lower.startswith("nt:"):
                result["service_type"] = line.split(":", 1)[1].strip()
    except Exception as e:
        logger.debug("ssdp_extraction_error", error=str(e))
    return result


def extract_dhcp(packet) -> dict:
    """Extract DHCP hostname, vendor class, and requested IP."""
    result = {"message_type": None, "hostname": None, "vendor_class": None,
              "requested_ip": None, "client_mac": None}
    try:
        from scapy.layers.dhcp import DHCP, BOOTP
        if not packet.haslayer(DHCP):
            return result
        bootp = packet[BOOTP]
        client_mac = bootp.chaddr
        if isinstance(client_mac, bytes):
            result["client_mac"] = ":".join(f"{b:02x}" for b in client_mac[:6])
        dhcp = packet[DHCP]
        _msg_types = {1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 4: "DECLINE",
                      5: "ACK", 6: "NAK", 7: "RELEASE", 8: "INFORM"}
        for option in dhcp.options:
            if isinstance(option, tuple) and len(option) >= 2:
                name, value = option[0], option[1]
                if name == "message-type":
                    result["message_type"] = _msg_types.get(value, f"TYPE_{value}")
                elif name == "hostname":
                    result["hostname"] = value.decode("utf-8", errors="ignore") if isinstance(value, bytes) else str(value)
                elif name == "vendor_class_id":
                    result["vendor_class"] = value.decode("utf-8", errors="ignore") if isinstance(value, bytes) else str(value)
                elif name == "requested_addr":
                    result["requested_ip"] = str(value)
            elif option == "end":
                break
    except Exception as e:
        logger.debug("dhcp_extraction_error", error=str(e))
    return result


def enrich_packet(packet) -> dict:
    """
    Run all relevant extractors on a packet and return consolidated metadata.
    This is the main entry point called by the sniffer on each packet.
    """
    enrichment = {}
    is_discovery = False
    try:
        from scapy.layers.l2 import ARP
        from scapy.layers.inet import TCP, UDP
        from scapy.layers.dns import DNS

        # ARP
        if packet.haslayer(ARP):
            arp_data = extract_arp(packet)
            if arp_data["operation"]:
                enrichment.update({
                    "arp_operation": arp_data["operation"],
                    "arp_sender_mac": arp_data["sender_mac"],
                    "arp_sender_ip": arp_data["sender_ip"],
                    "arp_target_ip": arp_data["target_ip"],
                })
                is_discovery = True

        # DNS / mDNS
        if packet.haslayer(DNS):
            if packet.haslayer(UDP):
                udp = packet[UDP]
                if udp.dport == 5353 or udp.sport == 5353:
                    mdns_data = extract_mdns(packet)
                    if mdns_data["hostname"] or mdns_data["service_type"]:
                        enrichment["_mdns"] = mdns_data
                        is_discovery = True
                else:
                    dns_data = extract_dns(packet)
                    if dns_data["query_name"]:
                        enrichment["dns_query"] = dns_data["query_name"]
                        if dns_data["answers"]:
                            enrichment["dns_answers"] = dns_data["answers"]

        # SSDP (UDP 1900)
        if packet.haslayer(UDP):
            udp = packet[UDP]
            if udp.dport == 1900 or udp.sport == 1900:
                ssdp_data = extract_ssdp(packet)
                if ssdp_data["method"]:
                    enrichment["_ssdp"] = ssdp_data
                    is_discovery = True

        # DHCP (UDP 67/68)
        if packet.haslayer(UDP):
            udp = packet[UDP]
            if udp.dport in (67, 68) or udp.sport in (67, 68):
                dhcp_data = extract_dhcp(packet)
                if dhcp_data["message_type"]:
                    enrichment["_dhcp"] = dhcp_data
                    is_discovery = True

        # HTTP / TLS
        if packet.haslayer(TCP):
            payload = bytes(packet[TCP].payload)
            if len(payload) > 16:
                start = payload[:8].decode("ascii", errors="ignore")
                if any(start.startswith(m) for m in
                       ("GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ", "PATCH ")):
                    http_data = extract_http(packet)
                    if http_data["method"]:
                        enrichment["http_method"] = http_data["method"]
                        enrichment["http_uri"] = http_data["uri"]
                        enrichment["http_host"] = http_data["host"]
                        enrichment["http_user_agent"] = http_data["user_agent"]
                elif len(payload) >= 6 and payload[0] == 0x16 and payload[5] == 0x01:
                    tls_data = extract_tls_sni(packet)
                    if tls_data["sni"]:
                        enrichment["tls_sni"] = tls_data["sni"]
                        enrichment["tls_version"] = tls_data["tls_version"]

        enrichment["is_discovery_relevant"] = is_discovery
    except Exception as e:
        logger.debug("packet_enrichment_error", error=str(e))
    return enrichment
