package com.charonsecurity.homora.ui.devices

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.FindingType
import com.charonsecurity.homora.data.AppState
import com.charonsecurity.homora.data.HistoryKind
import com.charonsecurity.homora.data.ScanState
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.ui.components.EmptyState
import com.charonsecurity.homora.ui.components.PlainCard
import com.charonsecurity.homora.ui.components.ScanControl
import com.charonsecurity.homora.ui.components.SectionHeader
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.icon
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.components.relativeTime
import com.charonsecurity.homora.ui.components.text
import com.charonsecurity.homora.ui.theme.LocalStatusColors

/** The name to show: the user's own label first, then the best announced name. */
@Composable
fun deviceName(d: Device, state: AppState): String = when {
    d.isSelf -> stringResource(R.string.kind_this_phone)
    else -> state.known[d.identityKey]?.label ?: d.bestName ?: if (d.isGateway) stringResource(R.string.kind_router) else stringResource(R.string.device_unnamed)
}

fun isMarked(d: Device, state: AppState) = d.isSelf || d.isGateway || d.identityKey in state.known

@Composable
fun DevicesScreen(container: AppContainer, onOpen: (String) -> Unit, onLockout: () -> Unit) {
    val scanState by container.scans.state.collectAsStateWithLifecycle()
    val app by container.store.state.collectAsStateWithLifecycle()
    val scan = app.lastScan

    LazyColumn(Modifier.fillMaxSize()) {
        item {
            if (scan != null || scanState !is ScanState.Idle) {
                ScanControl(scanState, scan?.at, onScan = container.scans::start, onStop = container.scans::cancel)
            }
        }
        if (scan == null) {
            if (scanState !is ScanState.Running) {
                item {
                    EmptyState(Icons.Outlined.Devices, stringResource(R.string.devices_empty_title), stringResource(R.string.devices_empty_body)) {
                        Button(onClick = container.scans::start) { Text(stringResource(R.string.action_scan)) }
                    }
                }
            }
            return@LazyColumn
        }
        val issuesByDevice = scan.findings.groupBy { it.deviceKey }
        val (marked, unmarked) = scan.devices.partition { isMarked(it, app) }

        if (unmarked.isNotEmpty()) {
            item {
                PlainCard(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.Top) {
                        Icon(Icons.Outlined.Info, null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text(pluralStringResource(R.plurals.devices_unmarked, unmarked.size, unmarked.size), style = MaterialTheme.typography.titleSmall)
                            Spacer(Modifier.height(4.dp))
                            Text(stringResource(R.string.devices_unmarked_hint), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            item { SectionHeader(stringResource(R.string.devices_section_unmarked)) }
            items(unmarked, key = { "u" + it.identityKey + it.ip }) { d -> DeviceRow(d, app, issuesByDevice[d.identityKey]?.map { it.type }, onOpen) }
        }
        item { SectionHeader(stringResource(R.string.devices_section_known)) }
        items(marked.sortedBy { if (it.isGateway) 0 else if (it.isSelf) 1 else 2 }, key = { "k" + it.identityKey + it.ip }) { d ->
            DeviceRow(d, app, issuesByDevice[d.identityKey]?.map { it.type }, onOpen)
        }

        if (app.history.isNotEmpty()) {
            item { SectionHeader(stringResource(R.string.history_title)) }
            items(app.history.take(8)) { e ->
                val subject = FindingType.entries.firstOrNull { it.name == e.subject }?.let { stringResource(it.text().title) } ?: e.subject
                ListItem(
                    headlineContent = {
                        Text(
                            when (e.kind) {
                                HistoryKind.NEW_DEVICE -> stringResource(R.string.history_new_device, subject)
                                HistoryKind.ISSUE_FOUND -> stringResource(R.string.history_issue_found, subject)
                                HistoryKind.ISSUE_FIXED -> stringResource(R.string.history_issue_fixed, subject)
                            },
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    },
                    supportingContent = { Text(relativeTime(e.at), style = MaterialTheme.typography.bodySmall) },
                )
            }
        }
        item {
            TextButton(onClick = onLockout, modifier = Modifier.fillMaxWidth().padding(16.dp)) { Text(stringResource(R.string.lockout_link)) }
        }
    }
}

@Composable
private fun DeviceRow(d: Device, app: AppState, issues: List<FindingType>?, onOpen: (String) -> Unit) {
    val status = LocalStatusColors.current
    ListItem(
        modifier = Modifier.clickable { onOpen(d.identityKey) }.padding(horizontal = 4.dp),
        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surface),
        leadingContent = { Icon(d.kind.icon(), null, tint = MaterialTheme.colorScheme.onSurfaceVariant) },
        headlineContent = { Text(deviceName(d, app)) },
        supportingContent = { Text(if (d.isSelf) d.ip else stringResource(d.kind.label()) + " · " + d.ip, style = MaterialTheme.typography.bodySmall) },
        trailingContent = issues?.takeIf { it.isNotEmpty() }?.let { list ->
            { StatusDot(if (list.any { it.severity.ordinal == 0 }) status.high else status.medium) }
        },
    )
}
