package com.focusforge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    var armed by remember { mutableStateOf(false) }
                    Column(
                        Modifier.fillMaxSize().padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Text("FocusForge", style = MaterialTheme.typography.headlineLarge)
                        Text(if (armed) "Focus session armed" else "Your phone, rebuilt for studying.")
                        Button(onClick = { armed = !armed }) {
                            Text(if (armed) "Cancel session" else "Start focus")
                        }
                    }
                }
            }
        }
    }
}
