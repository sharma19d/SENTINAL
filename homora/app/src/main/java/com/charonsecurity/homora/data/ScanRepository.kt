package com.charonsecurity.homora.data

import com.charonsecurity.homora.checks.Checks
import com.charonsecurity.homora.checks.Finding
import com.charonsecurity.homora.checks.SecurityReport
import com.charonsecurity.homora.net.Ipv4
import com.charonsecurity.homora.net.ScanOutcome
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.wifi.WifiAnalysis
import com.charonsecurity.homora.wifi.WifiReader
import com.charonsecurity.homora.wifi.WifiSecurityInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicInteger

/** Runs one scan at a time in an app-wide scope and saves the result. */
class ScanRepository(private val store: Store, private val wifi: WifiReader) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val generation = AtomicInteger()
    private var job: Job? = null

    private val _state = MutableStateFlow<ScanState>(ScanState.Idle)
    val state: StateFlow<ScanState> = _state.asStateFlow()

    fun start() {
        if (job?.isActive == true) return
        val gen = generation.incrementAndGet()
        _state.value = ScanState.Running(Scanner.Progress(Scanner.Phase.DISCOVERING, 0f, 0))
        job = scope.launch {
            try {
                run(gen)
            } catch (e: CancellationException) {
                set(gen, ScanState.Idle)
                throw e
            } catch (_: Exception) {
                Telemetry.scanFailed(Telemetry.ScanFailure.ERROR)
                set(gen, ScanState.Failed(Telemetry.ScanFailure.ERROR))
            }
        }
    }

    fun cancel() {
        generation.incrementAndGet() // late updates from the cancelled scan are ignored
        job?.cancel()
        job = null
        if (_state.value is ScanState.Running) _state.value = ScanState.Idle
    }

    /** The security report for a stored scan (same checks, so finding ids match). */
    fun report(scan: StoredScan?): SecurityReport? = scan?.let { Checks.evaluate(it.devices, it.wifi) }

    private fun set(gen: Int, s: ScanState) {
        if (generation.get() == gen) _state.value = s
    }

    private suspend fun run(gen: Int) {
        val lan = withContext(Dispatchers.IO) { wifi.lanInfo() }
        if (lan == null) return fail(gen, Telemetry.ScanFailure.NO_WIFI)
        if (!Ipv4.isPrivate(lan.selfIp) || Ipv4.scanRange(lan.selfIp, lan.prefixLength).isEmpty()) {
            return fail(gen, Telemetry.ScanFailure.NOT_PRIVATE_NETWORK)
        }
        val security = withContext(Dispatchers.IO) {
            wifi.connection()?.let { c -> WifiAnalysis.security(c.securityType, WifiAnalysis.ownAccessPoint(c, wifi.accessPoints())?.capabilities) }
        }
        val lock = Any()
        var best = 0f
        val outcome = Scanner(wifi::bindToWifi).scan(lan) { p ->
            // Progress arrives from many threads at once; never let the bar jump backwards.
            synchronized(lock) {
                if (p.fraction >= best) {
                    best = p.fraction
                    set(gen, ScanState.Running(p))
                }
            }
        }
        val report = Checks.evaluate(outcome.devices, security)
        store.update { applyScan(it, outcome, report.findings, security) }
        Telemetry.scanCompleted(
            outcome.durationMs,
            outcome.devices.size,
            outcome.devices.count { it.isUnidentified },
            report.findings.size,
        )
        set(gen, ScanState.Idle)
    }

    private fun fail(gen: Int, reason: Telemetry.ScanFailure) {
        Telemetry.scanFailed(reason)
        set(gen, ScanState.Failed(reason))
    }

    companion object {
        private const val MAX_HISTORY = 50

        /**
         * Folds a finished scan into the stored state and records what changed.
         * The first scan is the baseline, so it adds no history.
         */
        fun applyScan(state: AppState, outcome: ScanOutcome, findings: List<Finding>, wifi: WifiSecurityInfo? = null): AppState {
            val at = outcome.startedAt + outcome.durationMs
            val prev = state.lastScan
            val events = ArrayList<HistoryEvent>()
            if (prev != null) {
                outcome.devices
                    .filter { !it.isSelf && !it.isGateway && it.identityKey !in state.seenKeys && it.identityKey !in state.known }
                    .forEach { events += HistoryEvent(at, HistoryKind.NEW_DEVICE, it.bestName ?: it.ip) }
                val prevIds = prev.findings.map { it.id }.toSet()
                val newIds = findings.map { it.id }.toSet()
                val present = outcome.devices.map { it.identityKey }.toSet()
                findings.filter { it.id !in prevIds }.forEach { events += HistoryEvent(at, HistoryKind.ISSUE_FOUND, it.type.name) }
                // Only call an issue fixed when its device was seen again; a device that's
                // simply switched off hasn't fixed anything.
                prev.findings
                    .filter { it.id !in newIds && (it.deviceKey == null || it.deviceKey in present) }
                    .forEach { events += HistoryEvent(at, HistoryKind.ISSUE_FIXED, it.type.name) }
            }
            return state.copy(
                seenKeys = state.seenKeys + outcome.devices.map { it.identityKey },
                lastScan = StoredScan(at, outcome.durationMs, outcome.devices, findings, wifi),
                history = (events + state.history).take(MAX_HISTORY),
            )
        }
    }
}
