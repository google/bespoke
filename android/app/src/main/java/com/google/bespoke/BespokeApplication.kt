package com.google.bespoke

import android.app.Application
import com.google.bespoke.data.CrashLogger

class BespokeApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashLogger.install(this)
        val freedBytes = CrashLogger.cleanTemporaryFiles(this)
        if (freedBytes > 0) {
            CrashLogger.logInfo(this, "Application", "Cleaned orphaned temporary files (${freedBytes / (1024 * 1024)} MB freed)")
        }
    }
}
