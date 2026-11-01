package com.charonsecurity.homora.ui

import android.net.Uri
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.ui.devices.DeviceDetailScreen
import com.charonsecurity.homora.ui.devices.DevicesScreen
import com.charonsecurity.homora.ui.devices.IdentifyScreen
import com.charonsecurity.homora.ui.onboarding.OnboardingScreen
import com.charonsecurity.homora.ui.security.FindingScreen
import com.charonsecurity.homora.ui.security.LockoutScreen
import com.charonsecurity.homora.ui.security.SecurityScreen
import com.charonsecurity.homora.ui.settings.FeedbackScreen
import com.charonsecurity.homora.ui.settings.SettingsScreen
import com.charonsecurity.homora.ui.wifi.SmartHelperScreen
import com.charonsecurity.homora.ui.wifi.WifiScreen

object Routes {
    const val DEVICES = "devices"
    const val SECURITY = "security"
    const val WIFI = "wifi"
    const val SETTINGS = "settings"
    const val FEEDBACK = "feedback"
    const val LOCKOUT = "lockout"
    const val SMART = "smart"
    const val DEVICE = "device/{key}"
    const val IDENTIFY = "identify/{key}"
    const val FINDING = "finding/{id}"

    fun device(key: String) = "device/" + Uri.encode(key)
    fun identify(key: String) = "identify/" + Uri.encode(key)
    fun finding(id: String) = "finding/" + Uri.encode(id)
}

private data class Tab(val route: String, val label: Int, val icon: ImageVector)

private val TABS = listOf(
    Tab(Routes.DEVICES, R.string.nav_devices, Icons.Outlined.Devices),
    Tab(Routes.SECURITY, R.string.nav_security, Icons.Outlined.Shield),
    Tab(Routes.WIFI, R.string.nav_wifi, Icons.Outlined.Wifi),
)

@Composable
fun HomoraRoot(container: AppContainer) {
    val onboarded by container.prefs.onboarded.collectAsStateWithLifecycle()
    if (!onboarded) OnboardingScreen(container) else MainNav(container)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainNav(container: AppContainer) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    val isTab = TABS.any { it.route == route }

    Scaffold(
        // Detail screens bring their own Scaffold, which handles the system bars.
        contentWindowInsets = if (isTab) ScaffoldDefaults.contentWindowInsets else WindowInsets(0, 0, 0, 0),
        topBar = {
            if (isTab) {
                TopAppBar(
                    title = { Text(stringResource(R.string.app_name)) },
                    actions = {
                        IconButton(onClick = { nav.navigate(Routes.SETTINGS) }) {
                            Icon(Icons.Outlined.Settings, stringResource(R.string.settings))
                        }
                    },
                )
            }
        },
        bottomBar = {
            if (isTab) {
                NavigationBar {
                    TABS.forEach { tab ->
                        NavigationBarItem(
                            selected = route == tab.route,
                            onClick = { nav.switchTab(tab.route) },
                            icon = { Icon(tab.icon, null) },
                            label = { Text(stringResource(tab.label)) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(nav, startDestination = Routes.DEVICES, modifier = Modifier.padding(padding)) {
            composable(Routes.DEVICES) {
                DevicesScreen(container, onOpen = { nav.navigate(Routes.device(it)) }, onLockout = { nav.navigate(Routes.LOCKOUT) })
            }
            composable(Routes.SECURITY) {
                SecurityScreen(container, onOpen = { nav.navigate(Routes.finding(it)) })
            }
            composable(Routes.WIFI) {
                WifiScreen(container, onSmartHelper = { nav.navigate(Routes.SMART) })
            }
            composable(Routes.SETTINGS) {
                SettingsScreen(container, onBack = nav::popBackStack, onFeedback = { nav.navigate(Routes.FEEDBACK) })
            }
            composable(Routes.FEEDBACK) { FeedbackScreen(container, onBack = nav::popBackStack) }
            composable(Routes.LOCKOUT) {
                LockoutScreen(onBack = nav::popBackStack, onRescan = {
                    container.scans.start()
                    nav.switchTab(Routes.DEVICES)
                })
            }
            composable(Routes.SMART) { SmartHelperScreen(container, onBack = nav::popBackStack) }
            composable(Routes.DEVICE) { e ->
                val key = Uri.decode(e.arguments?.getString("key").orEmpty())
                DeviceDetailScreen(
                    container, key, onBack = nav::popBackStack,
                    onIdentify = { nav.navigate(Routes.identify(key)) },
                    onFinding = { nav.navigate(Routes.finding(it)) },
                )
            }
            composable(Routes.IDENTIFY) { e ->
                IdentifyScreen(container, Uri.decode(e.arguments?.getString("key").orEmpty()), onBack = nav::popBackStack)
            }
            composable(Routes.FINDING) { e ->
                FindingScreen(container, Uri.decode(e.arguments?.getString("id").orEmpty()), onBack = nav::popBackStack, onRescan = {
                    container.scans.start()
                    nav.switchTab(Routes.SECURITY)
                })
            }
        }
    }
}

private fun NavHostController.switchTab(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
