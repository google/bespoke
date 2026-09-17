package com.google.bespoke.data

import android.content.Context
import android.os.Build
import android.os.StatFs
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CrashLogger {
    private const val TAG = "BespokeCrashLogger"
    private const val CRASH_LOG_FILE = "crash.log"
    private const val EVENTS_LOG_FILE = "app_events.log"
    private const val MAX_LOG_SIZE_BYTES = 100 * 1024 // 100 KB max to prevent disk saturation

    private var isInstalled = false
    private var defaultExceptionHandler: Thread.UncaughtExceptionHandler? = null

    @Synchronized
    fun install(context: Context) {
        if (isInstalled) return
        isInstalled = true
        val appContext = context.applicationContext ?: context

        defaultExceptionHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                recordCrash(appContext, thread, throwable)
            } catch (t: Throwable) {
                try {
                    Log.e(TAG, "Failed recording crash in CrashLogger", t)
                } catch (_: Throwable) {}
            } finally {
                defaultExceptionHandler?.uncaughtException(thread, throwable)
            }
        }
    }

    fun recordCrash(context: Context, thread: Thread, throwable: Throwable) {
        try {
            val sw = StringWriter()
            val pw = PrintWriter(sw)
            throwable.printStackTrace(pw)
            pw.flush()
            val stackTrace = sw.toString()

            val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)
            val timestamp = dateFormat.format(Date())

            val runtime = Runtime.getRuntime()
            val maxMemMb = runtime.maxMemory() / (1024 * 1024)
            val totalMemMb = runtime.totalMemory() / (1024 * 1024)
            val freeMemMb = runtime.freeMemory() / (1024 * 1024)
            val usedMemMb = totalMemMb - freeMemMb

            val freeDiskMb = try { context.filesDir.freeSpace / (1024 * 1024) } catch (_: Throwable) { -1L }

            val sb = StringBuilder()
            sb.appendLine("================== FATAL CRASH ==================")
            sb.appendLine("Timestamp:   $timestamp")
            sb.appendLine("Thread:      ${thread.name} (id: ${thread.id})")
            sb.appendLine("Exception:   ${throwable.javaClass.name}: ${throwable.message}")
            sb.appendLine("Memory:      Used: ${usedMemMb}MB / Total: ${totalMemMb}MB / Max: ${maxMemMb}MB")
            sb.appendLine("Free Disk:   ${freeDiskMb}MB free internal storage")
            sb.appendLine("Device:      ${Build.MANUFACTURER} ${Build.MODEL} (Android ${Build.VERSION.RELEASE}, API ${Build.VERSION.SDK_INT})")
            sb.appendLine("------------------- STACKTRACE -------------------")
            sb.appendLine(stackTrace.trimEnd())
            sb.appendLine("==================================================")
            sb.appendLine()

            val crashText = sb.toString()

            // Write to internal storage
            val internalFile = File(context.filesDir, CRASH_LOG_FILE)
            appendWithRotation(internalFile, crashText)

            // Write to external files directory if available
            try {
                context.getExternalFilesDir(null)?.let { extDir ->
                    val extFile = File(extDir, CRASH_LOG_FILE)
                    appendWithRotation(extFile, crashText)
                }
            } catch (_: Throwable) {}

            Log.e(TAG, "Fatal crash logged:\n$crashText")
        } catch (_: Throwable) {}
    }

    fun logError(context: Context?, tag: String, message: String, throwable: Throwable? = null) {
        try {
            if (throwable != null) {
                Log.e(tag, message, throwable)
            } else {
                Log.e(tag, message)
            }

            if (context != null) {
                val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
                val timestamp = dateFormat.format(Date())
                val sb = StringBuilder()
                sb.append("[$timestamp] [ERROR] [$tag] $message\n")
                if (throwable != null) {
                    val sw = StringWriter()
                    val pw = PrintWriter(sw)
                    throwable.printStackTrace(pw)
                    pw.flush()
                    sb.append(sw.toString().trimEnd()).append("\n")
                }

                val internalFile = File(context.filesDir, EVENTS_LOG_FILE)
                appendWithRotation(internalFile, sb.toString())
            }
        } catch (_: Throwable) {}
    }

    fun logInfo(context: Context?, tag: String, message: String) {
        try {
            Log.i(tag, message)
            if (context != null) {
                val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
                val timestamp = dateFormat.format(Date())
                val line = "[$timestamp] [INFO] [$tag] $message\n"
                val internalFile = File(context.filesDir, EVENTS_LOG_FILE)
                appendWithRotation(internalFile, line)
            }
        } catch (_: Throwable) {}
    }

    private fun appendWithRotation(file: File, text: String) {
        try {
            if (file.exists() && file.length() > MAX_LOG_SIZE_BYTES) {
                val existing = file.readText(Charsets.UTF_8)
                val trimmed = existing.takeLast(MAX_LOG_SIZE_BYTES / 2)
                file.writeText(trimmed + text, Charsets.UTF_8)
            } else {
                FileOutputStream(file, true).use { fos ->
                    fos.write(text.toByteArray(Charsets.UTF_8))
                    fos.flush()
                }
            }
        } catch (_: Throwable) {}
    }

    fun hasCrashLog(context: Context): Boolean {
        val internal = File(context.filesDir, CRASH_LOG_FILE)
        val ext = context.getExternalFilesDir(null)?.let { File(it, CRASH_LOG_FILE) }
        return (internal.exists() && internal.length() > 0) || (ext?.exists() == true && ext.length() > 0)
    }

    fun getRawCrashLog(context: Context): String? {
        val internal = File(context.filesDir, CRASH_LOG_FILE)
        val ext = context.getExternalFilesDir(null)?.let { File(it, CRASH_LOG_FILE) }
        return when {
            internal.exists() && internal.length() > 0 -> internal.readText(Charsets.UTF_8)
            ext?.exists() == true && ext.length() > 0 -> ext.readText(Charsets.UTF_8)
            else -> null
        }
    }

    fun cleanTemporaryFiles(context: Context): Long {
        var reclaimed = 0L
        try {
            val partFiles = context.filesDir.listFiles { _, name -> name.endsWith(".part") } ?: emptyArray()
            for (f in partFiles) {
                val len = f.length()
                if (f.delete()) {
                    reclaimed += len
                }
            }
            context.getExternalFilesDir(null)?.let { extDir ->
                val extPartFiles = extDir.listFiles { _, name -> name.endsWith(".part") } ?: emptyArray()
                for (f in extPartFiles) {
                    val len = f.length()
                    if (f.delete()) {
                        reclaimed += len
                    }
                }
            }
        } catch (_: Throwable) {}
        return reclaimed
    }

    fun getDiagnosticsAndLogs(context: Context): String {
        val sb = StringBuilder()
        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
        val currentTime = dateFormat.format(Date())

        sb.appendLine("================ BESPOKE DIAGNOSTICS ================")
        sb.appendLine("Current Time:  $currentTime")
        sb.appendLine("Device:        ${Build.MANUFACTURER} ${Build.MODEL}")
        sb.appendLine("Android OS:    Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")

        // Storage Info
        try {
            val stat = StatFs(context.filesDir.absolutePath)
            val availableBytes = stat.availableBlocksLong * stat.blockSizeLong
            val totalBytes = stat.blockCountLong * stat.blockSizeLong
            val avail = availableBytes / (1024 * 1024)
            val totalMb = totalBytes / (1024 * 1024)
            sb.appendLine("Internal Disk: Free ${avail}MB / Total ${totalMb}MB")
        } catch (_: Throwable) {
            val avail = context.filesDir.freeSpace / (1024 * 1024)
            sb.appendLine("Internal Disk: Free ${avail}MB")
        }

        // JVM Heap Info
        try {
            val runtime = Runtime.getRuntime()
            val maxMb = runtime.maxMemory() / (1024 * 1024)
            val totalMb = runtime.totalMemory() / (1024 * 1024)
            val freeMb = runtime.freeMemory() / (1024 * 1024)
            val usedMb = totalMb - freeMb
            sb.appendLine("JVM Heap:      Used ${usedMb}MB / Alloc ${totalMb}MB / Max ${maxMb}MB")
        } catch (_: Throwable) {}

        // Installed DB Decks
        try {
            val dbFiles = context.filesDir.listFiles { _, name -> name.endsWith(".db") } ?: emptyArray()
            sb.appendLine("Stored Decks:  ${dbFiles.size} (.db files in internal storage)")
            for (f in dbFiles) {
                val sizeMb = f.length().toDouble() / (1024 * 1024)
                sb.appendLine("  - ${f.name} (%.2f MB)".format(Locale.US, sizeMb))
            }
        } catch (_: Throwable) {}

        sb.appendLine()

        // 1. Crash Logs
        val crashContent = getRawCrashLog(context)
        if (!crashContent.isNullOrBlank()) {
            sb.appendLine("----------------- FATAL CRASH LOGS -----------------")
            sb.appendLine(crashContent.trim())
            sb.appendLine()
        } else {
            sb.appendLine("No fatal crashes recorded.")
            sb.appendLine()
        }

        // 2. Events & Error Logs
        val eventsFile = File(context.filesDir, EVENTS_LOG_FILE)
        if (eventsFile.exists() && eventsFile.length() > 0) {
            sb.appendLine("-------------- RECENT EVENTS & ERRORS --------------")
            sb.appendLine(eventsFile.readText(Charsets.UTF_8).trim())
            sb.appendLine()
        } else {
            sb.appendLine("No recent error events recorded.")
            sb.appendLine()
        }

        sb.appendLine("=====================================================")
        return sb.toString()
    }

    fun clearLogs(context: Context) {
        try {
            File(context.filesDir, CRASH_LOG_FILE).delete()
            File(context.filesDir, EVENTS_LOG_FILE).delete()
            context.getExternalFilesDir(null)?.let { extDir ->
                File(extDir, CRASH_LOG_FILE).delete()
                File(extDir, EVENTS_LOG_FILE).delete()
            }
        } catch (_: Throwable) {}
    }
}
