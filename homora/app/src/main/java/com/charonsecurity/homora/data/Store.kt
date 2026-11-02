package com.charonsecurity.homora.data

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import java.io.File

/**
 * All device data in one private JSON file. The file is read on a background
 * thread so opening the app never waits on disk; writes are atomic (temp file
 * + rename) so a crash mid-write can't corrupt it.
 */
class Store(context: Context) {
    private val file = File(context.filesDir, FILE_NAME)
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val mutex = Mutex()
    private val io = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> = _state.asStateFlow()

    private val loaded: Deferred<Unit> = io.async {
        read()?.let { _state.value = it }
    }

    /** Waits until the file has been read. Call before reading [state] outside the UI. */
    suspend fun awaitLoaded() = loaded.await()

    suspend fun update(change: (AppState) -> AppState) {
        loaded.await()
        mutex.withLock {
            val old = _state.value
            val new = change(old)
            if (new == old) return
            _state.value = new
            withContext(Dispatchers.IO) { write(new) }
        }
    }

    suspend fun setKnown(key: String, label: String) = update {
        it.copy(known = it.known + (key to KnownDevice(key, label.trim().take(60))))
    }

    /** Marks a device as one the user wants off the network (or clears that). */
    suspend fun setBlocked(key: String, on: Boolean) = update {
        it.copy(blocked = if (on) it.blocked + (key to System.currentTimeMillis()) else it.blocked - key)
    }

    suspend fun forget(key: String) = update { it.copy(known = it.known - key) }

    /** Saves a spot; a spot with the same name replaces the old reading. */
    suspend fun addRoom(room: RoomReading) = update { s ->
        s.copy(rooms = s.rooms.filterNot { it.name.equals(room.name, ignoreCase = true) } + room)
    }

    suspend fun deleteRoom(name: String) = update { s -> s.copy(rooms = s.rooms.filterNot { it.name == name }) }

    suspend fun clearAll() = update { AppState() }

    private fun read(): AppState? = try {
        if (file.exists()) json.decodeFromString(AppState.serializer(), file.readText()) else null
    } catch (_: Exception) {
        null // unreadable or from an incompatible version: start fresh rather than crash
    }

    private fun write(s: AppState) {
        try {
            val tmp = File(file.parentFile, "$FILE_NAME.tmp")
            tmp.writeText(json.encodeToString(AppState.serializer(), s))
            if (!tmp.renameTo(file)) {
                file.delete()
                tmp.renameTo(file)
            }
        } catch (_: Exception) {
            // Disk full or similar: the in-memory state is still correct for this session.
        }
    }

    private companion object {
        const val FILE_NAME = "homora_state.json"
    }
}
