package com.charonsecurity.homora.ui.devices

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.Severity
import com.charonsecurity.homora.data.AppState
import com.charonsecurity.homora.data.ScanState
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.DeviceKind
import com.charonsecurity.homora.ui.components.EmptyState
import com.charonsecurity.homora.ui.components.GlassCard
import com.charonsecurity.homora.ui.components.GlowButton
import com.charonsecurity.homora.ui.components.PillChip
import com.charonsecurity.homora.ui.components.ScanControl
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.TabHeader
import com.charonsecurity.homora.ui.components.icon
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.theme.LocalStatusColors

enum class DeviceFilter { ALL, MINE, UNKNOWN }

/** The user's label or the best announced name, without any fallback text. */
fun namedAs(d: Device, state: AppState): String? = state.known[d.identityKey]?.label ?: d.bestName

/** The name to show: the user's own label first, then the best announced name. */
@Composable
fun deviceName(d: Device, state: AppState): String = when {
    d.isSelf -> stringResource(R.string.kind_this_phone)
    else -> namedAs(d, state) ?: if (d.isGateway) stringResource(R.string.kind_router) else stringResource(R.string.device_unnamed)
}

fun isMarked(d: Device, state: AppState) = d.isSelf || d.isGateway || d.identityKey in state.known

@Composable
fun DevicesScreen(
    container: AppContainer,
    filter: DeviceFilter,
    onFilter: (DeviceFilter) -> Unit,
    onOpen: (String) -> Unit,
    onLockout: () -> Unit,
) {
    val scanState by container.scans.state.collectAsStateWithLifecycle()
    val app by container.store.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scan = app.lastScan
    var searching by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }

    // Sorted once per scan or label change, not on every frame.
    val all = remember(scan, app.known) {
        scan?.devices.orEmpty().sortedWith(
            compareBy<Device>(
                { if (it.isGateway) 0 else if (it.isSelf) 1 else if (isMarked(it, app)) 2 else 3 },
                { namedAs(it, app)?.lowercase() ?: "￿" },
                { it.ip.substringAfterLast('.').toIntOrNull() ?: 0 },
            ),
        )
    }
    val mineCount = remember(all) { all.count { isMarked(it, app) } }
    val unknownCount = all.size - mineCount
    val issues = remember(scan) { scan?.findings.orEmpty().groupBy { it.deviceKey } }
    val shown = remember(all, filter, query) {
        val q = query.trim().lowercase()
        all.filter {
            when (filter) {
                DeviceFilter.ALL -> true
                DeviceFilter.MINE -> isMarked(it, app)
                DeviceFilter.UNKNOWN -> !isMarked(it, app)
            }
        }.filter { d ->
            q.isEmpty() || d.ip.contains(q) || namedAs(d, app)?.lowercase()?.contains(q) == true ||
                context.getString(d.kind.label()).lowercase().contains(q)
        }
    }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item(key = "header") {
            TabHeader(stringResource(R.string.nav_devices)) {
                if (scan != null) {
                    IconButton(onClick = container.scans::start, enabled = scanState !is ScanState.Running) {
                        Icon(Icons.Outlined.Refresh, stringResource(R.string.action_rescan))
                    }
                    IconButton(onClick = { searching = !searching; if (!searching) query = "" }) {
                        Icon(if (searching) Icons.Outlined.Close else Icons.Outlined.Search, stringResource(R.string.devices_search))
                    }
                }
            }
        }
        item(key = "search") {
            AnimatedVisibility(searching, enter = expandVertically() + fadeIn(), exit = shrinkVertically() + fadeOut()) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it.take(40) },
                    singleLine = true,
                    placeholder = { Text(stringResource(R.string.devices_search_hint)) },
                    leadingIcon = { Icon(Icons.Outlined.Search, null) },
                    shape = RoundedCornerShape(50),
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedBorderColor = Color.White.copy(alpha = 0.14f),
                        focusedBorderColor = Color.White.copy(alpha = 0.5f),
                    ),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
        }
        if (scan != null) {
            item(key = "chips") {
                Row(
                    Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    PillChip(stringResource(R.string.devices_filter_all, all.size), filter == DeviceFilter.ALL, { onFilter(DeviceFilter.ALL) })
                    PillChip(stringResource(R.string.devices_filter_mine, mineCount), filter == DeviceFilter.MINE, { onFilter(DeviceFilter.MINE) })
                    PillChip(stringResource(R.string.devices_filter_unknown, unknownCount), filter == DeviceFilter.UNKNOWN, { onFilter(DeviceFilter.UNKNOWN) })
                }
            }
        }
        if (scanState !is ScanState.Idle) {
            item(key = "scan") { ScanControl(scanState, scan?.at, onScan = container.scans::start, onStop = container.scans::cancel) }
        }
        if (scan == null) {
            if (scanState !is ScanState.Running) {
                item(key = "empty") {
                    EmptyState(Icons.Outlined.Devices, stringResource(R.string.devices_empty_title), stringResource(R.string.devices_empty_body)) {
                        GlowButton(stringResource(R.string.action_scan), container.scans::start, Modifier.padding(horizontal = 24.dp))
                    }
                }
            }
            return@LazyColumn
        }
        if (filter == DeviceFilter.UNKNOWN && unknownCount > 0 && query.isBlank()) {
            item(key = "hint") {
                GlassCard(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp)) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.Top) {
                        Icon(Icons.Outlined.Info, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(12.dp))
                        Text(stringResource(R.string.devices_unmarked_hint), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        if (shown.isEmpty()) {
            item(key = "none") {
                Text(
                    stringResource(if (query.isBlank()) R.string.devices_none_in_filter else R.string.devices_no_match),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 24.dp),
                )
            }
        }
        items(shown, key = { it.identityKey + "|" + it.ip }) { d ->
            DeviceCard(
                d, app, issues[d.identityKey]?.minOfOrNull { it.type.severity.ordinal }, onOpen,
                Modifier.animateItem().padding(horizontal = 16.dp, vertical = 5.dp),
            )
        }
        item(key = "lockout") {
            Box(Modifier.fillMaxWidth().padding(top = 8.dp), contentAlignment = Alignment.Center) {
                TextButton(onClick = onLockout) { Text(stringResource(R.string.lockout_link)) }
            }
        }
    }
}

@Composable
private fun DeviceCard(d: Device, app: AppState, worstIssue: Int?, onOpen: (String) -> Unit, modifier: Modifier = Modifier) {
    val status = LocalStatusColors.current
    GlassCard(modifier.fillMaxWidth(), onClick = { onOpen(d.identityKey) }) {
        Row(Modifier.padding(horizontal = 18.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(d.kind.icon(), null, Modifier.size(30.dp), tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.9f))
            Spacer(Modifier.width(18.dp))
            Column(Modifier.weight(1f)) {
                Text(deviceName(d, app), style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    if (d.isSelf || d.kind == DeviceKind.UNKNOWN) d.ip else stringResource(d.kind.label()),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            if (worstIssue != null) {
                StatusDot(if (worstIssue == Severity.HIGH.ordinal) status.high else status.medium)
                Spacer(Modifier.width(10.dp))
            } else if (!isMarked(d, app)) {
                StatusDot(Color.White.copy(alpha = 0.7f))
                Spacer(Modifier.width(10.dp))
            }
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
