package com.google.bespoke.audio

interface AudioPlayer {
    fun playBytes(audioBytes: ByteArray, onComplete: (() -> Unit)? = null)
    fun playFile(filePath: String, onComplete: (() -> Unit)? = null)
    fun stop()
    fun isPlaying(): Boolean
    fun release()
}
