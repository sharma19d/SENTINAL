package com.charonsecurity.homora.checks

/**
 * The single "network health" number on the home screen. It is a summary,
 * not a measurement: it starts at 100 and loses points for each problem,
 * weighted by severity, and a little for devices nobody has recognised yet.
 */
object Health {
    enum class Level { SECURE, FAIR, AT_RISK }

    fun score(findings: List<Finding>, unmarkedDevices: Int): Int {
        var s = 100
        for (f in findings) {
            s -= when (f.type.severity) {
                Severity.HIGH -> 18
                Severity.MEDIUM -> 8
                Severity.LOW -> 3
            }
        }
        s -= (unmarkedDevices * 2).coerceAtMost(10)
        return s.coerceIn(5, 100)
    }

    fun level(score: Int): Level = when {
        score >= 80 -> Level.SECURE
        score >= 55 -> Level.FAIR
        else -> Level.AT_RISK
    }
}
