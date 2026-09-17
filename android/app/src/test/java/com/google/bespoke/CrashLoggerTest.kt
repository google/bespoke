package com.google.bespoke

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.google.bespoke.data.CrashLogger
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class CrashLoggerTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        CrashLogger.clearLogs(context)
    }

    @Test
    fun testRecordCrashCreatesFormattedCrashLog() {
        assertFalse(CrashLogger.hasCrashLog(context))

        val dummyException = RuntimeException("Simulated fatal test exception", IllegalStateException("Root cause"))
        CrashLogger.recordCrash(context, Thread.currentThread(), dummyException)

        assertTrue(CrashLogger.hasCrashLog(context))
        val rawLog = CrashLogger.getRawCrashLog(context)
        assertNotNull(rawLog)
        assertTrue(rawLog!!.contains("FATAL CRASH"))
        assertTrue(rawLog.contains("Simulated fatal test exception"))
        assertTrue(rawLog.contains("Root cause"))
        assertTrue(rawLog.contains(Thread.currentThread().name))
        assertTrue(rawLog.contains("Memory:"))
        assertTrue(rawLog.contains("Device:"))
    }

    @Test
    fun testLogErrorAndInfoAppendsToEvents() {
        CrashLogger.logInfo(context, "TestTag", "Application started successfully")
        CrashLogger.logError(context, "ImportTag", "Failed to parse corrupt card", IllegalArgumentException("Invalid format"))

        val diagnostics = CrashLogger.getDiagnosticsAndLogs(context)
        assertTrue(diagnostics.contains("BESPOKE DIAGNOSTICS"))
        assertTrue(diagnostics.contains("Application started successfully"))
        assertTrue(diagnostics.contains("Failed to parse corrupt card"))
        assertTrue(diagnostics.contains("Invalid format"))
    }

    @Test
    fun testDiagnosticsContainsSystemMemoryAndStorage() {
        val diagnostics = CrashLogger.getDiagnosticsAndLogs(context)
        assertTrue(diagnostics.contains("Internal Disk:"))
        assertTrue(diagnostics.contains("JVM Heap:"))
        assertTrue(diagnostics.contains("Device:"))
    }

    @Test
    fun testClearLogsDeletesAllLogFiles() {
        CrashLogger.recordCrash(context, Thread.currentThread(), RuntimeException("Crash to be deleted"))
        CrashLogger.logError(context, "TestTag", "Error to be deleted")

        assertTrue(CrashLogger.hasCrashLog(context))

        CrashLogger.clearLogs(context)

        assertFalse(CrashLogger.hasCrashLog(context))
        val diagnostics = CrashLogger.getDiagnosticsAndLogs(context)
        assertTrue(diagnostics.contains("No fatal crashes recorded."))
    }

    @Test
    fun testCleanTemporaryFilesRemovesPartFiles() {
        val partFile1 = File(context.filesDir, "test_deck.part")
        partFile1.writeText("sample partial content", Charsets.UTF_8)
        assertTrue(partFile1.exists())

        val freed = CrashLogger.cleanTemporaryFiles(context)
        assertTrue(freed > 0)
        assertFalse(partFile1.exists())
    }

    @Test
    fun testDeleteStoredDeck() {
        val dbFile = File(context.filesDir, "custom_deck.db")
        dbFile.writeText("dummy db content", Charsets.UTF_8)
        assertTrue(dbFile.exists())

        val deckInfo = com.google.bespoke.model.DeckInfo(
            id = "custom_deck.db",
            title = "Custom",
            targetLanguage = "Custom",
            nativeLanguage = "English",
            file = dbFile
        )
        val deleted = com.google.bespoke.data.DeckRepository.deleteDeck(context, deckInfo)
        assertTrue(deleted)
        assertFalse(dbFile.exists())
    }
}
