package com.charonsecurity.homora.feedback

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.tasks.await

internal object FeedbackBackend {
    suspend fun submit(doc: Map<String, Any>) {
        val auth = FirebaseAuth.getInstance()
        val uid = (auth.currentUser ?: auth.signInAnonymously().await().user)?.uid ?: error("sign-in failed")
        FirebaseFirestore.getInstance().collection("feedback")
            .add(doc + mapOf("uid" to uid, "createdAt" to FieldValue.serverTimestamp()))
            .await()
    }
}
