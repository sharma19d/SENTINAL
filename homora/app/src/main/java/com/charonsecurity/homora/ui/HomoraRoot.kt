package com.charonsecurity.homora.ui

import android.net.Uri
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.ui.devices.DeviceDetailScreen
import com.charonsecurity.homora.ui.devices.DeviceFilter
import com.charonsecurity.homora.ui.devices.DevicesScreen
import com.charonsecurity.homora.ui.devices.IdentifyScreen
import com.charonsecurity.homora.ui.home.HomeScreen
import com.charonsecurity.homora.ui.onboarding.OnboardingScreen
import com.charonsecurity.homora.ui.security.FindingScreen
import com.charonsecurity.homora.ui.security.LockoutScreen
import com.charonsecurity.homora.ui.security.SecurityScreen
import com.charonsecurity.homora.ui.settings.FeedbackScreen
import com.charonsecurity.homora.ui.settings.SettingsScreen
import com.charonsecurity.homora.ui.wifi.SmartHelperScreen
import com.charonsecurity.homora.ui.wifi.WifiScreen

object Routes {
    const val HOME = "home"
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
    Tab(Routes.HOME, R.string.nav_home, Icons.Outlined.Home),
    Tab(Routes.DEVICES, R.string.nav_devices, Icons.Outlined.Devices),
    Tab(Routes.SECURITY, R.string.nav_security, Icons.Outlined.Shield),
    Tab(Routes.WIFI, R.string.nav_wifi, Icons.Outlined.Wifi),
)
private val TAB_ROUTES = TABS.map { it.route }.toSet()

private fun NavBackStackEntry.isTab() = destination.route in TAB_ROUTES

@Composable
fun HomoraRoot(container: AppContainer) {
    val onboarded by container.prefs.onboarded.collectAsStateWithLifecycle()
    AnimatedContent(
        targetState = onboarded,
        transitionSpec = { fadeIn(tween(450, delayMillis = 100)) togetherWith fadeOut(tween(250)) },
        label = "root",
    ) { done ->
        if (done) MainNav(container) else OnboardingScreen(container)
    }
}

@Composable
private fun MainNav(container: AppContainer) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route ?: Routes.HOME
    val isTab = route in TAB_ROUTES
    var deviceFilter by rememberSaveable { mutableStateOf(DeviceFilter.ALL) }

    fun openDevices(filter: DeviceFilter) {
        deviceFilter = filter
        nav.switchTab(Routes.DEVICES)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        // Detail screens bring their own Scaffold, which handles the system bars.
        contentWindowInsets = if (isTab) ScaffoldDefaults.contentWindowInsets else WindowInsets(0, 0, 0, 0),
        bottomBar = {
            AnimatedVisibility(
                visible = isTab,
                enter = slideInVertically(tween(220)) { it } + fadeIn(tween(220)),
                exit = slideOutVertically(tween(180)) { it } + fadeOut(tween(150)),
            ) {
                BottomBar(route) { nav.switchTab(it) }
            }
        },
    ) { padding ->
        NavHost(
            nav,
            startDestination = Routes.HOME,
            modifier = Modifier.padding(padding),
            // Short, light transitions: tabs cross-fade, detail screens slide in a little.
            enterTransition = {
                if (targetState.isTab() && initialState.isTab()) fadeIn(tween(200))
                else fadeIn(tween(220)) + slideInHorizontally(tween(280, easing = FastOutSlowInEasing)) { it / 10 }
            },
            exitTransition = { fadeOut(tween(160)) },
            popEnterTransition = { fadeIn(tween(220)) },
            popExitTransition = {
                if (targetState.isTab() && initialState.isTab()) fadeOut(tween(160))
                else fadeOut(tween(180)) + slideOutHorizontally(tween(240, easing = FastOutSlowInEasing)) { it / 10 }
            },
        ) {
            composable(Routes.HOME) {
                HomeScreen(
                    container,
                    onSettings = { nav.navigate(Routes.SETTINGS) },
                    onDevices = ::openDevices,
                    onSecurity = { nav.switchTab(Routes.SECURITY) },
                    onWifi = { nav.switchTab(Routes.WIFI) },
                    onLockout = { nav.navigate(Routes.LOCKOUT) },
                    onDevice = { nav.navigate(Routes.device(it)) },
                    onFinding = { nav.navigate(Routes.finding(it)) },
                )
            }
            composable(Routes.DEVICES) {
                DevicesScreen(
                    container,
                    filter = deviceFilter,
                    onFilter = { deviceFilter = it },
                    onOpen = { nav.navigate(Routes.device(it)) },
                    onLockout = { nav.navigate(Routes.LOCKOUT) },
                )
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
                    nav.switchTab(Routes.HOME)
                })
            }
            composable(Routes.SMART) { SmartHelperScreen(container, onBack = nav::popBackStack) }
            composable(Routes.DEVICE) { e ->
                val key = Uri.decode(e.arguments?.getString("key").orEmpty())
                DeviceDetailScreen(
                    container, key, onBack = nav::popBackStack,
                    onIdentify = { nav.navigate(Routes.identify(key)) },
                    onFinding = { nav.navigate(Routes.finding(it)) },
                    onBlock = { nav.navigate(Routes.LOCKOUT) },
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

/** Icon-only tab bar from the design: the selected tab is white with a short bar under it. */
@Composable
private fun BottomBar(current: String, onSelect: (String) -> Unit) {
    val shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
    Box(
        Modifier
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(MaterialTheme.colorScheme.surfaceContainerHigh, MaterialTheme.colorScheme.surfaceContainerLow)), shape)
            .border(1.dp, Color.White.copy(alpha = 0.07f), shape)
            .navigationBarsPadding(),
    ) {
        Row(Modifier.fillMaxWidth().height(68.dp), verticalAlignment = Alignment.CenterVertically) {
            TABS.forEach { tab ->
                val selected = current == tab.route
                val tint by animateColorAsState(
                    if (selected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.75f),
                    tween(200),
                    label = "tabTint",
                )
                val bar by animateDpAsState(if (selected) 26.dp else 0.dp, tween(220), label = "tabBar")
                Column(
                    Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .selectable(selected = selected, role = Role.Tab, onClick = { if (!selected) onSelect(tab.route) }),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                ) {
                    Icon(tab.icon, contentDescription = stringResource(tab.label), tint = tint, modifier = Modifier.size(26.dp))
                    Spacer(Modifier.height(8.dp))
                    Box(Modifier.width(bar).height(3.dp).background(MaterialTheme.colorScheme.onSurface, RoundedCornerShape(50)))
                }
            }
        }
    }
}

private fun NavHostController.switchTab(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
