package com.google.bespoke.audio

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.ByteArrayDataSource
import androidx.media3.datasource.DataSource
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.ProgressiveMediaSource
import java.io.File

class ExoAudioPlayer(private val context: Context) : AudioPlayer {
    private val tag = "BespokeAudioPlayer"

    private var exoPlayer: ExoPlayer? = null
    private var currentCompletionCallback: (() -> Unit)? = null
    private var isCurrentlyPlaying = false

    init {
        try {
            val player = getOrCreatePlayer()
            preWarmAudioPipeline(player)
        } catch (e: Exception) {
            Log.w(tag, "Failed pre-warming ExoPlayer", e)
        }
    }

    override fun preWarm() {
        try {
            val player = getOrCreatePlayer()
            preWarmAudioPipeline(player)
        } catch (e: Exception) {
            Log.w(tag, "Failed pre-warming ExoPlayer", e)
        }
    }

    private fun preWarmAudioPipeline(player: ExoPlayer) {
        try {
            // A minimal 44-byte valid silent WAV header with 0 samples
            val silentWav = byteArrayOf(
                0x52, 0x49, 0x46, 0x46, // "RIFF"
                0x24, 0x00, 0x00, 0x00, // file size - 8 = 36
                0x57, 0x41, 0x56, 0x45, // "WAVE"
                0x66, 0x6d, 0x74, 0x20, // "fmt "
                0x10, 0x00, 0x00, 0x00, // chunk size 16
                0x01, 0x00,             // PCM format
                0x01, 0x00,             // 1 channel (mono)
                0x44, 0xac.toByte(), 0x00, 0x00, // 44100 Hz sample rate
                0x88.toByte(), 0x58, 0x01, 0x00, // byte rate (44100 * 2)
                0x02, 0x00,             // block align 2
                0x10, 0x00,             // 16 bits per sample
                0x64, 0x61, 0x74, 0x61, // "data"
                0x00, 0x00, 0x00, 0x00  // 0 data bytes
            )
            val dataSourceFactory = DataSource.Factory { ByteArrayDataSource(silentWav) }
            val mediaItem = MediaItem.Builder()
                .setUri(Uri.parse("data:audio/wav;base64,"))
                .setMimeType(MimeTypes.AUDIO_WAV)
                .build()
            val mediaSource = ProgressiveMediaSource.Factory(dataSourceFactory)
                .createMediaSource(mediaItem)

            player.volume = 0f
            player.setMediaSource(mediaSource)
            player.prepare()
            player.stop()
            player.volume = 1f
            Log.d(tag, "Audio pipeline pre-warmed successfully in-memory")
        } catch (e: Exception) {
            Log.w(tag, "Audio pipeline pre-warm completed with notice", e)
        }
    }

    private fun getOrCreatePlayer(): ExoPlayer {
        val existing = exoPlayer
        if (existing != null) return existing

        val audioAttributes = AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
            .build()

        // Configure smooth low-latency playback
        val loadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(
                500,  // minBufferMs
                2000, // maxBufferMs
                250,  // bufferForPlaybackMs
                500   // bufferForPlaybackAfterRebufferMs
            )
            .build()

        val player = ExoPlayer.Builder(context)
            .setAudioAttributes(audioAttributes, true)
            .setLoadControl(loadControl)
            .build()

        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED) {
                    isCurrentlyPlaying = false
                    currentCompletionCallback?.invoke()
                    currentCompletionCallback = null
                }
            }

            override fun onPlayerError(error: PlaybackException) {
                Log.e(tag, "ExoPlayer playback error: ${error.errorCodeName}", error)
                isCurrentlyPlaying = false
                currentCompletionCallback?.invoke()
                currentCompletionCallback = null
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                isCurrentlyPlaying = isPlaying
            }
        })
        exoPlayer = player
        return player
    }

    override fun playBytes(audioBytes: ByteArray, onComplete: (() -> Unit)?) {
        if (audioBytes.isEmpty()) {
            onComplete?.invoke()
            return
        }

        try {
            val player = getOrCreatePlayer()
            currentCompletionCallback = onComplete

            val dataSourceFactory = DataSource.Factory {
                ByteArrayDataSource(audioBytes)
            }
            val mediaItem = MediaItem.Builder()
                .setUri(Uri.parse("data:audio/ogg;base64,"))
                .setMimeType(MimeTypes.AUDIO_OGG)
                .build()
            val mediaSource = ProgressiveMediaSource.Factory(dataSourceFactory)
                .createMediaSource(mediaItem)

            player.stop()
            player.setMediaSource(mediaSource)
            player.playWhenReady = true
            player.prepare()
            isCurrentlyPlaying = true
        } catch (e: Exception) {
            Log.e(tag, "Failed playing audio bytes in memory", e)
            onComplete?.invoke()
        }
    }

    override fun playFile(filePath: String, onComplete: (() -> Unit)?) {
        try {
            val file = File(filePath)
            val canonicalPath = file.canonicalPath
            val allowedCache = context.cacheDir.canonicalPath
            val allowedFiles = context.filesDir.canonicalPath
            if (!canonicalPath.startsWith(allowedCache) && !canonicalPath.startsWith(allowedFiles)) {
                Log.w(tag, "Access to unauthorized audio file path blocked: $filePath")
                onComplete?.invoke()
                return
            }
            if (!file.exists()) {
                Log.w(tag, "Audio file does not exist: $filePath")
                onComplete?.invoke()
                return
            }

            val player = getOrCreatePlayer()
            currentCompletionCallback = onComplete
            val uri = Uri.fromFile(file)
            val mediaItem = MediaItem.Builder()
                .setUri(uri)
                .setMimeType(MimeTypes.AUDIO_OGG)
                .build()

            player.stop()
            player.setMediaItem(mediaItem)
            player.playWhenReady = true
            player.prepare()
            isCurrentlyPlaying = true
        } catch (e: Exception) {
            Log.e(tag, "Failed playing audio file: $filePath", e)
            onComplete?.invoke()
        }
    }

    override fun stop() {
        try {
            exoPlayer?.stop()
            isCurrentlyPlaying = false
            currentCompletionCallback = null
        } catch (_: Exception) {}
    }

    override fun isPlaying(): Boolean {
        return isCurrentlyPlaying || (exoPlayer?.isPlaying ?: false)
    }

    override fun release() {
        try {
            exoPlayer?.release()
            exoPlayer = null
            isCurrentlyPlaying = false
            currentCompletionCallback = null
        } catch (_: Exception) {}
    }
}
