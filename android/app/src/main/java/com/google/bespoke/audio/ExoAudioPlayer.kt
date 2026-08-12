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
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest

class ExoAudioPlayer(private val context: Context) : AudioPlayer {
    private val tag = "BespokeAudioPlayer"

    private var exoPlayer: ExoPlayer? = null
    private var currentCompletionCallback: (() -> Unit)? = null
    private var isCurrentlyPlaying = false

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

    private fun pruneCacheIfNeeded(maxSizeBytes: Long = 20 * 1024 * 1024) {
        val cacheFiles = context.cacheDir.listFiles { _, name -> name.startsWith("audio_") } ?: return
        var totalSize = cacheFiles.sumOf { it.length() }
        if (totalSize > maxSizeBytes) {
            cacheFiles.sortBy { it.lastModified() }
            for (file in cacheFiles) {
                if (totalSize <= maxSizeBytes) break
                totalSize -= file.length()
                file.delete()
            }
        }
    }

    override fun playBytes(audioBytes: ByteArray, onComplete: (() -> Unit)?) {
        if (audioBytes.isEmpty()) {
            onComplete?.invoke()
            return
        }

        try {
            pruneCacheIfNeeded()
            // Write audio bytes to a cached temp file
            val hash = MessageDigest.getInstance("SHA-256")
                .digest(audioBytes)
                .joinToString("") { "%02x".format(it) }
            val tempFile = File(context.cacheDir, "audio_$hash.ogg")
            if (!tempFile.exists() || tempFile.length() != audioBytes.size.toLong()) {
                FileOutputStream(tempFile).use { fos ->
                    fos.write(audioBytes)
                    fos.flush()
                    fos.fd.sync()
                }
            }

            playFile(tempFile.absolutePath, onComplete)
        } catch (e: Exception) {
            Log.e(tag, "Failed playing audio bytes", e)
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
