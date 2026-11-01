package com.charonsecurity.homora

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.charonsecurity.homora.ui.HomoraRoot
import com.charonsecurity.homora.ui.theme.HomoraTheme

class MainActivity : ComponentActivity() {
    private val container get() = (application as HomoraApp).container

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            HomoraTheme {
                HomoraRoot(container)
            }
        }
    }

    override fun onStop() {
        super.onStop()
        // Nothing runs while the app isn't on screen.
        if (!isChangingConfigurations) container.scans.cancel()
    }
}
