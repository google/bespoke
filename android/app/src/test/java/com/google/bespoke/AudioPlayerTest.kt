package com.google.bespoke

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.audio.AudioPlayer
import com.google.bespoke.audio.ExoAudioPlayer
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class AudioPlayerTest {

    private lateinit var context: Context
    private lateinit var audioPlayer: AudioPlayer

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        audioPlayer = ExoAudioPlayer(context)
    }

    @Test
    fun testPlayBytesAndCacheCreation() {
        val dummyAudio = "OggS_TEST_AUDIO_BYTES".toByteArray(Charsets.UTF_8)
        audioPlayer.playBytes(dummyAudio)

        // Cache file should be generated in cacheDir
        val cacheFiles = context.cacheDir.listFiles { _, name -> name.startsWith("audio_") && name.endsWith(".ogg") }
        assertNotNull(cacheFiles)
        assertTrue(cacheFiles!!.isNotEmpty())
    }

    @Test
    fun testEmptyBytesInvokesCallback() {
        var completed = false
        audioPlayer.playBytes(ByteArray(0)) {
            completed = true
        }
        assertTrue(completed)
    }

    @Test
    fun testMissingFileInvokesCallback() {
        var completed = false
        val missingFile = File(context.cacheDir, "non_existent_audio.ogg")
        audioPlayer.playFile(missingFile.absolutePath) {
            completed = true
        }
        assertTrue(completed)
    }

    @Test
    fun testUnauthorizedFileBlocked() {
        var completed = false
        audioPlayer.playFile("/system/etc/hosts") {
            completed = true
        }
        assertTrue(completed)
    }

    @Test
    fun testStopAndRelease() {
        audioPlayer.stop()
        assertFalse(audioPlayer.isPlaying())
        audioPlayer.release()
    }
}
