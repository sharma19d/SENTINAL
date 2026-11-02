package com.charonsecurity.homora.ui.security

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.Finding
import com.charonsecurity.homora.checks.Severity
import com.charonsecurity.homora.data.ScanState
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.DetailScaffold
import com.charonsecurity.homora.ui.components.EmptyState
import com.charonsecurity.homora.ui.components.ExpandableCard
import com.charonsecurity.homora.ui.components.GlassCard
import com.charonsecurity.homora.ui.components.GlowButton
import com.charonsecurity.homora.ui.components.TabHeader
import com.charonsecurity.homora.ui.components.NumberedSteps
import com.charonsecurity.homora.ui.components.PlainCard
import com.charonsecurity.homora.ui.components.ScanControl
import com.charonsecurity.homora.ui.components.SectionHeader
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.components.text
import com.charonsecurity.homora.ui.theme.LocalStatusColors

@Composable
private fun severityColor(s: Severity) = LocalStatusColors.current.let {
    when (s) {
        Severity.HIGH -> it.high
        Severity.MEDIUM -> it.medium
        Severity.LOW -> MaterialTheme.colorScheme.outline
    }
}

@Composable
fun SecurityScreen(container: AppContainer, onOpen: (String) -> Unit) {
    val scanState by container.scans.state.collectAsStateWithLifecycle()
    val app by container.store.state.collectAsStateWithLifecycle()
    val scan = app.lastScan
    val report = remember(scan) { container.scans.report(scan) }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item(key = "header") { TabHeader(stringResource(R.string.nav_security)) }
        if (scan != null || scanState !is ScanState.Idle) {
            item(key = "scan") { ScanControl(scanState, scan?.at, onScan = container.scans::start, onStop = container.scans::cancel) }
        }
        if (report == null) {
            if (scanState !is ScanState.Running) {
                item(key = "empty") {
                    EmptyState(Icons.Outlined.Shield, stringResource(R.string.security_empty_title), stringResource(R.string.security_empty)) {
                        GlowButton(stringResource(R.string.action_scan), container.scans::start, Modifier.padding(horizontal = 24.dp))
                    }
                }
            }
            return@LazyColumn
        }
        item(key = "summary") {
            val n = report.findings.size
            Text(
                if (n == 0) stringResource(R.string.security_all_good) else pluralStringResource(R.plurals.security_issues, n, n),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
            )
        }
        items(report.findings, key = { it.id }) { f -> FindingRow(f, onOpen, Modifier.animateItem()) }
        if (report.passed.isNotEmpty()) {
            item(key = "passedHeader") { SectionHeader(stringResource(R.string.security_passed)) }
            item(key = "passed") {
                GlassCard(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                    Column(Modifier.padding(vertical = 6.dp)) {
                        report.passed.forEach { c ->
                            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.CheckCircle, null, tint = LocalStatusColors.current.good, modifier = Modifier.size(20.dp))
                                Spacer(Modifier.width(12.dp))
                                Text(stringResource(c.label()), style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FindingRow(f: Finding, onOpen: (String) -> Unit, modifier: Modifier = Modifier) {
    GlassCard(modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 5.dp), onClick = { onOpen(f.id) }) {
        Row(Modifier.padding(horizontal = 18.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            StatusDot(severityColor(f.type.severity), Modifier.size(12.dp))
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(stringResource(f.type.text().title), style = MaterialTheme.typography.bodyLarge)
                val sub = listOfNotNull(stringResource(f.type.severity.label()), f.deviceName ?: f.deviceIp).joinToString(" · ")
                Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun FindingScreen(container: AppContainer, id: String, onBack: () -> Unit, onRescan: () -> Unit) {
    val app by container.store.state.collectAsStateWithLifecycle()
    val finding = app.lastScan?.findings?.firstOrNull { it.id == id }
    var disputed by rememberSaveable(id) { mutableStateOf(false) }
    var rated by rememberSaveable(id) { mutableStateOf(false) }
    LaunchedEffect(finding?.type) { finding?.type?.let(Telemetry::fixGuideOpened) }

    DetailScaffold(finding?.let { stringResource(it.type.text().title) } ?: "", onBack) { padding ->
        if (finding == null) return@DetailScaffold
        val t = finding.type.text()
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusDot(severityColor(finding.type.severity))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(finding.type.severity.label()), style = MaterialTheme.typography.labelLarge)
            }
            (finding.deviceName ?: finding.deviceIp)?.let {
                Spacer(Modifier.height(4.dp))
                Text(stringResource(R.string.finding_on_device, it), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.finding_fix), style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(10.dp))
            NumberedSteps(stringArrayResource(t.steps).toList())
            Spacer(Modifier.height(16.dp))
            ExpandableCard(stringResource(R.string.finding_why)) {
                Text(stringResource(t.why), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(24.dp))
            GlowButton(stringResource(R.string.finding_rescan), onRescan)
            Spacer(Modifier.height(24.dp))

            PlainCard {
                Column(Modifier.padding(16.dp)) {
                    if (!rated) {
                        Text(stringResource(R.string.finding_helpful), style = MaterialTheme.typography.bodyMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = { rated = true; Telemetry.guideHelpful(finding.type, true) }) { Text(stringResource(R.string.yes)) }
                            TextButton(onClick = { rated = true; Telemetry.guideHelpful(finding.type, false) }) { Text(stringResource(R.string.no)) }
                        }
                    } else {
                        Text(stringResource(R.string.finding_helpful_thanks), style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            if (!disputed) {
                OutlinedButton(onClick = { disputed = true; Telemetry.findingDisputed(finding.type) }) {
                    Text(stringResource(R.string.finding_dispute))
                }
            } else {
                Text(stringResource(R.string.finding_disputed_thanks), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun LockoutScreen(onBack: () -> Unit, onRescan: () -> Unit) {
    LaunchedEffect(Unit) { Telemetry.lockoutGuideOpened() }
    DetailScaffold(stringResource(R.string.lockout_title), onBack) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
            NumberedSteps(stringArrayResource(R.array.lockout_steps).toList())
            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.lockout_note), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(24.dp))
            GlowButton(stringResource(R.string.action_rescan), onRescan)
        }
    }
}
