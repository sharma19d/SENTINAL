package com.charonsecurity.homora.ui.devices

import androidx.compose.foundation.BorderStroke
import android.content.ActivityNotFoundException
import android.content.Intent
import androidx.core.net.toUri
import androidx.compose.material.icons.outlined.Speed
import androidx.compose.material.icons.outlined.Lan
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.outlined.OpenInBrowser
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringArrayResource
import com.charonsecurity.homora.checks.DeviceRisk
import com.charonsecurity.homora.checks.Isolation
import com.charonsecurity.homora.ui.components.ExpandableCard
import com.charonsecurity.homora.ui.components.GlowButton
import com.charonsecurity.homora.ui.components.NumberedSteps
import com.charonsecurity.homora.ui.components.Tag
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Block
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.checks.Severity
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.DetailScaffold
import com.charonsecurity.homora.ui.components.GlassCard
import com.charonsecurity.homora.ui.components.IconTile
import com.charonsecurity.homora.ui.components.ServiceInfo
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.icon
import com.charonsecurity.homora.ui.components.identitySource
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.components.serviceInfo
import com.charonsecurity.homora.ui.components.text
import com.charonsecurity.homora.ui.theme.LocalStatusColors
import kotlinx.coroutines.launch

@Composable
fun DeviceDetailScreen(
    container: AppContainer,
    key: String,
    onBack: () -> Unit,
    onIdentify: () -> Unit,
    onFinding: (String) -> Unit,
    onBlock: () -> Unit = {},
) {
    val app by container.store.state.collectAsStateWithLifecycle()
    val device = app.lastScan?.devices?.firstOrNull { it.identityKey == key }
    val scope = rememberCoroutineScope()
    var naming by rememberSaveable { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    var blockSheet by rememberSaveable { mutableStateOf(false) }
    val known = app.known[key]
    val editable = device != null && !device.isSelf && !device.isGateway

    DetailScaffold(
        title = "",
        onBack = onBack,
        actions = {
            if (editable) {
                Box {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Outlined.MoreVert, stringResource(R.string.detail_more)) }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(
                            text = { Text(stringResource(if (known == null) R.string.detail_mark_known else R.string.detail_rename)) },
                            onClick = { menu = false; naming = true },
                        )
                        if (known != null) {
                            DropdownMenuItem(
                                text = { Text(stringResource(R.string.detail_forget)) },
                                onClick = { menu = false; scope.launch { container.store.forget(key) } },
                            )
                        }
                        DropdownMenuItem(text = { Text(stringResource(R.string.detail_find)) }, onClick = { menu = false; onIdentify() })
                    }
                }
            }
        },
    ) { padding ->
        if (device == null) {
            Text(
                stringResource(R.string.detail_gone),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(padding).padding(24.dp),
            )
            return@DetailScaffold
        }
        val findings = remember(app.lastScan, key) { app.lastScan?.findings.orEmpty().filter { it.deviceKey == key } }
        val status = LocalStatusColors.current
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            GlassCard(Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp)) {
                Row(Modifier.padding(horizontal = 20.dp, vertical = 26.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconTile(device.kind.icon(), size = 68.dp)
                    Spacer(Modifier.width(20.dp))
                    Column(Modifier.weight(1f)) {
                        Text(deviceName(device, app), style = MaterialTheme.typography.headlineSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Spacer(Modifier.height(4.dp))
                        Text(device.ip, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (editable && known == null) {
                            Spacer(Modifier.height(8.dp))
                            Text(stringResource(R.string.detail_not_marked), style = MaterialTheme.typography.labelMedium, color = status.medium)
                        }
                    }
                }
            }

            if (editable) {
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    ActionPill(
                        stringResource(if (known == null) R.string.detail_mark_known else R.string.detail_rename),
                        filled = known == null,
                        modifier = Modifier.weight(1f),
                    ) { naming = true }
                    ActionPill(stringResource(R.string.detail_find), filled = false, modifier = Modifier.weight(1f), onClick = onIdentify)
                }
            }

            if (!device.isSelf) {
                val risk = remember(app.lastScan, app.known, key) {
                    DeviceRisk.assess(device, app.lastScan?.findings.orEmpty(), isMarked(device, app), key in app.lastScan?.newKeys.orEmpty())
                }
                val riskColor = when (risk.level) {
                    DeviceRisk.Level.HIGH -> status.high
                    DeviceRisk.Level.MEDIUM -> status.medium
                    DeviceRisk.Level.LOW -> status.good
                }
                Spacer(Modifier.height(12.dp))
                ExpandableCard(
                    stringResource(R.string.risk_title),
                    icon = Icons.Outlined.Speed,
                    iconTint = riskColor,
                    trailing = { Tag(stringResource(risk.level.label()) + " · " + stringResource(R.string.risk_score, risk.score), riskColor) },
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (risk.reasons.isEmpty()) {
                            Text(stringResource(R.string.risk_none), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        risk.reasons.forEach { r ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                StatusDot(riskColor)
                                Spacer(Modifier.width(10.dp))
                                Text(stringResource(r.label()), style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
                Label(stringResource(R.string.detail_open_services))
                ServiceGrid(services(device))
            }

            if (findings.isNotEmpty()) {
                Label(stringResource(R.string.detail_issues))
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    findings.forEach { f ->
                        GlassCard(Modifier.fillMaxWidth(), onClick = { onFinding(f.id) }) {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                StatusDot(if (f.type.severity == Severity.HIGH) status.high else status.medium)
                                Spacer(Modifier.width(12.dp))
                                Text(stringResource(f.type.text().title), Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                                Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }

            val advice = remember(app.lastScan, app.known, key) {
                Isolation.advise(device, app.lastScan?.findings.orEmpty(), isMarked(device, app))
            }
            if (advice.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                ExpandableCard(
                    stringResource(R.string.iso_title),
                    icon = Icons.Outlined.Lan,
                    trailing = { Tag(pluralStringResource(R.plurals.iso_count, advice.size, advice.size), MaterialTheme.colorScheme.onSurfaceVariant) },
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        advice.forEachIndexed { i, a ->
                            val (t, b) = a.text()
                            Row {
                                Text("${i + 1}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(22.dp))
                                Column {
                                    Text(stringResource(t), style = MaterialTheme.typography.titleSmall)
                                    Spacer(Modifier.height(2.dp))
                                    Text(stringResource(b), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                }
            }

            if (editable) {
                val isBlocked = key in app.blocked
                Spacer(Modifier.height(12.dp))
                GlassCard(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Block, null, Modifier.size(22.dp), tint = if (isBlocked) status.high else MaterialTheme.colorScheme.onSurface)
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(stringResource(R.string.block_toggle), style = MaterialTheme.typography.bodyLarge)
                            Text(
                                stringResource(if (isBlocked) R.string.block_toggle_on else R.string.block_toggle_off),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Switch(
                            checked = isBlocked,
                            onCheckedChange = { on ->
                                scope.launch { container.store.setBlocked(key, on) }
                                if (on) blockSheet = true
                            },
                            colors = SwitchDefaults.colors(checkedTrackColor = status.high, checkedThumbColor = Color.White),
                        )
                    }
                }
            }

            Label(stringResource(R.string.detail_about))
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Field(stringResource(R.string.detail_type), stringResource(device.kind.label()))
                    Field(stringResource(R.string.detail_ip), device.ip)
                    device.manufacturer?.let { Field(stringResource(R.string.detail_maker), it) }
                    device.model?.let { Field(stringResource(R.string.detail_model), it) }
                    if (!device.isSelf) Field(stringResource(R.string.detail_seen_as), stringResource(device.identitySource()))
                }
            }

            if (!device.isSelf && device.bestName == null) {
                Spacer(Modifier.height(12.dp))
                ExpandableCard(stringResource(R.string.detail_why_unknown_title), icon = Icons.AutoMirrored.Outlined.HelpOutline) {
                    Text(stringResource(R.string.detail_why_unknown_body), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Spacer(Modifier.height(32.dp))
        }
        if (blockSheet) {
            BlockSheet(
                deviceName = deviceName(device, app),
                deviceIp = device.ip,
                router = app.lastScan?.devices?.firstOrNull { it.isGateway },
                onDismiss = { blockSheet = false },
            )
        }
        if (naming) {
            NameDialog(
                initial = known?.label ?: device.bestName.orEmpty(),
                onDismiss = { naming = false },
                onSave = { label ->
                    naming = false
                    scope.launch { container.store.setKnown(key, label) }
                    if (known == null) Telemetry.deviceMarkedKnown()
                },
            )
        }
    }
}

/** One tile per distinct service, UPnP port-forwarding included. */
private fun services(d: Device): List<ServiceInfo> {
    val list = d.openPorts.sorted().map(::serviceInfo).distinctBy { it.short }.toMutableList()
    if (Scanner.UPNP_IGD in d.services && list.none { it.short == "UPnP" }) list.add(0, serviceInfo(49152).copy(risky = true))
    return list
}

@Composable
private fun ServiceGrid(items: List<ServiceInfo>) {
    if (items.isEmpty()) {
        GlassCard(Modifier.fillMaxWidth()) {
            Text(
                stringResource(R.string.detail_no_services),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(18.dp),
            )
        }
        return
    }
    val status = LocalStatusColors.current
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items.chunked(3).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { s ->
                    GlassCard(Modifier.weight(1f).height(104.dp)) {
                        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                            Icon(s.icon, null, Modifier.size(28.dp), tint = if (s.risky) status.medium else MaterialTheme.colorScheme.onSurface)
                            Spacer(Modifier.height(10.dp))
                            Text(s.short, style = MaterialTheme.typography.labelLarge, maxLines = 1, textAlign = TextAlign.Center)
                        }
                    }
                }
                repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun ActionPill(text: String, filled: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val c = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(50),
        color = if (filled) c.primary else Color.Transparent,
        contentColor = if (filled) c.onPrimary else c.onSurface,
        border = if (filled) null else BorderStroke(1.dp, Color.White.copy(alpha = 0.18f)),
        modifier = modifier.height(48.dp),
    ) {
        Box(contentAlignment = Alignment.Center) { Text(text, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis) }
    }
}

@Composable
private fun Label(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 4.dp, top = 22.dp, bottom = 10.dp),
    )
}

@Composable
private fun Field(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
fun NameDialog(initial: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by rememberSaveable { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
        title = { Text(stringResource(R.string.detail_mark_known)) },
        text = {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it.take(60) },
                singleLine = true,
                placeholder = { Text(stringResource(R.string.detail_name_hint)) },
            )
        },
        confirmButton = { TextButton(onClick = { onSave(text.ifBlank { initial }) }, enabled = text.isNotBlank() || initial.isNotBlank()) { Text(stringResource(R.string.save)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}

internal fun Device.watchablePort(): Int? = openPorts.minOrNull()

/** The router's settings page, over HTTPS when the router offers it. */
private fun Device.adminUrl(): String =
    if (443 in openPorts || 8443 in openPorts) "https://$ip" + (if (443 in openPorts) "" else ":8443")
    else "http://$ip" + (if (80 in openPorts || 8080 !in openPorts) "" else ":8080")

/**
 * How to block a device, done the only way a phone app honestly can: in the
 * router. Detects the router, opens its settings page, and keeps the steps short.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BlockSheet(deviceName: String, deviceIp: String, router: Device?, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var error by remember { mutableStateOf<String?>(null) }
    val steps = stringArrayResource(R.array.block_steps).map { it.replace("%1\$s", deviceIp) }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surfaceContainerHigh) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp).padding(bottom = 28.dp)) {
            Text(stringResource(R.string.block_sheet_title, deviceName), style = MaterialTheme.typography.titleLarge)
            router?.let { r ->
                val name = listOfNotNull(r.manufacturer, r.upnpName ?: r.model ?: r.httpTitle).distinct().joinToString(" ").ifBlank { null }
                Spacer(Modifier.height(4.dp))
                Text(
                    stringResource(R.string.block_sheet_router, listOfNotNull(name, r.ip).joinToString(" · ")),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(14.dp))
            Text(stringResource(R.string.block_sheet_intro), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(16.dp))
            NumberedSteps(steps)
            Spacer(Modifier.height(22.dp))
            if (router != null) {
                val url = router.adminUrl()
                GlowButton(stringResource(R.string.block_open_router), onClick = {
                    try {
                        context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri()))
                    } catch (_: ActivityNotFoundException) {
                        error = context.getString(R.string.block_no_browser, url)
                    }
                }, icon = Icons.Outlined.OpenInBrowser)
                error?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
                Spacer(Modifier.height(8.dp))
            }
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.block_done)) }
        }
    }
}
