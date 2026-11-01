package com.charonsecurity.homora.net

/** UPnP/SSDP discovery messages and device descriptions. */
object Ssdp {
    const val ADDRESS = "239.255.255.250"
    const val PORT = 1900

    fun mSearch(searchTarget: String = "ssdp:all", mx: Int = 2): ByteArray = (
        "M-SEARCH * HTTP/1.1\r\n" +
            "HOST: $ADDRESS:$PORT\r\n" +
            "MAN: \"ssdp:discover\"\r\n" +
            "MX: $mx\r\n" +
            "ST: $searchTarget\r\n\r\n"
        ).toByteArray(Charsets.US_ASCII)

    data class Response(val location: String?, val server: String?, val st: String?, val usn: String?) {
        /** The device UUID from the USN ("uuid:…::urn:…"), stable across IP changes. */
        val uuid: String?
            get() = usn?.substringAfter("uuid:", "")?.substringBefore("::")?.lowercase()?.takeIf { it.isNotBlank() }

        /** True for a router advertising UPnP port-forwarding (Internet Gateway Device). */
        val isInternetGateway: Boolean
            get() = listOfNotNull(st, usn).any {
                it.contains("InternetGatewayDevice", true) ||
                    it.contains("WANIPConnection", true) || it.contains("WANPPPConnection", true)
            }
    }

    fun parseResponse(text: String): Response? {
        val lines = text.split("\r\n", "\n")
        val status = lines.firstOrNull() ?: return null
        if (!status.startsWith("HTTP/1.1 200") && !status.startsWith("NOTIFY")) return null
        val headers = HashMap<String, String>()
        for (line in lines.drop(1)) {
            val i = line.indexOf(':')
            if (i > 0) headers[line.substring(0, i).trim().uppercase()] = line.substring(i + 1).trim()
        }
        return Response(headers["LOCATION"], headers["SERVER"], headers["ST"] ?: headers["NT"], headers["USN"])
    }

    data class Description(
        val friendlyName: String?,
        val manufacturer: String?,
        val modelName: String?,
        val modelNumber: String?,
        val deviceType: String?,
    )

    /** Reads the root device's fields from a UPnP description XML (first occurrence wins). */
    fun parseDescription(xml: String): Description {
        fun tag(name: String) = Regex("<$name>\\s*([^<]{1,200}?)\\s*</$name>", RegexOption.IGNORE_CASE)
            .find(xml)?.groupValues?.get(1)?.let(::unescape)?.takeIf { it.isNotBlank() }
        return Description(tag("friendlyName"), tag("manufacturer"), tag("modelName"), tag("modelNumber"), tag("deviceType"))
    }

    private fun unescape(s: String) = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", "\"").replace("&apos;", "'")
}
