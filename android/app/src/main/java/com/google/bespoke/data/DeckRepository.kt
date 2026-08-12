package com.google.bespoke.data

import android.content.Context
import android.net.Uri
import android.util.Log
import com.google.bespoke.model.*
import com.google.bespoke.srs.DeckEngine
import java.io.File
import java.io.FileOutputStream

sealed class ImportResult {
    data class Success(val deckInfo: DeckInfo) : ImportResult()
    data class Failure(val message: String) : ImportResult()
}

object DeckRepository {
    private const val TAG = "BespokeDeckRepo"

    fun copyAssetIfNewer(context: Context, assetName: String): File {
        val targetFile = File(context.filesDir, assetName)
        var assetLength = -1L
        try {
            context.assets.openFd(assetName).use { fd ->
                assetLength = fd.length
            }
        } catch (_: Exception) {}

        if (!targetFile.exists() || (assetLength > 0 && targetFile.length() != assetLength)) {
            try {
                context.assets.open(assetName).use { input ->
                    FileOutputStream(targetFile).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        var bytesRead: Int
                        while (input.read(buffer).also { bytesRead = it } != -1) {
                            output.write(buffer, 0, bytesRead)
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed copying asset $assetName", e)
            }
        }
        return targetFile
    }

    fun importDeckFromUri(context: Context, uri: Uri): ImportResult {
        return try {
            val freeBytes = context.filesDir.freeSpace
            if (freeBytes < 20 * 1024 * 1024) {
                return ImportResult.Failure(
                    "Not enough internal storage (${freeBytes / (1024 * 1024)} MB free). Please wipe emulator data or free space."
                )
            }

            var rawName = getFileNameFromUri(context, uri) ?: "deck_${System.currentTimeMillis()}.db"
            if (!rawName.endsWith(".db", ignoreCase = true)) {
                rawName = "$rawName.db"
            }
            val sanitizedName = rawName.replace(Regex("[^a-zA-Z0-9._-]"), "_")
            val targetFile = File(context.filesDir, sanitizedName)

            Log.i(TAG, "Importing deck from URI '$uri' to '${targetFile.absolutePath}'")

            val inputStream = context.contentResolver.openInputStream(uri)
                ?: return ImportResult.Failure("Cannot open input stream for selected file.")

            inputStream.use { input ->
                FileOutputStream(targetFile).use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var bytesRead: Int
                    var totalCopied = 0L
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                        totalCopied += bytesRead
                    }
                    output.flush()
                    Log.i(TAG, "Copied $totalCopied bytes to ${targetFile.name}")
                }
            }

            val deckInfo = inspectDeckFile(context, targetFile, isAsset = false, assetName = null)
            if (deckInfo == null) {
                ImportResult.Failure("Failed to validate database schema. Please verify with 'maintainers/verify_package.py'.")
            } else {
                ImportResult.Success(deckInfo)
            }
        } catch (e: Exception) {
            val msg = when {
                e.message?.contains("ENOSPC", ignoreCase = true) == true ||
                e.message?.contains("space", ignoreCase = true) == true ->
                    "Out of storage space on device. Please wipe emulator data."
                else ->
                    "Import failed: ${e.localizedMessage ?: e.javaClass.simpleName}"
            }
            Log.e(TAG, msg, e)
            ImportResult.Failure(msg)
        }
    }

    private fun getFileNameFromUri(context: Context, uri: Uri): String? {
        var name: String? = null
        if (uri.scheme == "content") {
            try {
                val cursor = context.contentResolver.query(uri, null, null, null, null)
                cursor?.use {
                    if (it.moveToFirst()) {
                        val index = it.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                        if (index >= 0) {
                            name = it.getString(index)
                        }
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Error resolving display name from URI", e)
            }
        }
        if (name.isNullOrBlank()) {
            name = uri.lastPathSegment?.let { File(it).name }
        }
        return name
    }

    fun loadDeckFromDb(dbFile: File): Pair<DatasetReader, DeckEngine> {
        val reader = DatasetReader(dbFile)
        val deck = reader.createDeckEngine()
        return Pair(reader, deck)
    }

    fun loadBundledDeck(
        context: Context,
        assetName: String = "sample_deck.db"
    ): Pair<DatasetReader, DeckEngine> {
        val targetFile = copyAssetIfNewer(context, assetName)
        return loadDeckFromDb(targetFile)
    }

    fun listAvailableDecks(context: Context): List<DeckInfo> {
        val decks = mutableListOf<DeckInfo>()
        val seenFileNames = mutableSetOf<String>()

        // 1. Scan bundled asset databases (e.g. sample_deck.db)
        try {
            val assetFiles = context.assets.list("") ?: emptyArray()
            for (assetName in assetFiles) {
                if (assetName.endsWith(".db")) {
                    val file = copyAssetIfNewer(context, assetName)
                    seenFileNames.add(file.name)
                    val info = inspectDeckFile(context, file, isAsset = true, assetName = assetName)
                    if (info != null) {
                        decks.add(info)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error listing asset decks", e)
        }

        // 2. Scan internal app storage directory (/data/data/com.google.bespoke/files/)
        try {
            val files = context.filesDir.listFiles { _, name -> name.endsWith(".db") } ?: emptyArray()
            for (file in files) {
                if (file.name !in seenFileNames) {
                    val info = inspectDeckFile(context, file, isAsset = false, assetName = null)
                    if (info != null) {
                        decks.add(info)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error listing storage decks", e)
        }

        return decks
    }

    private fun inspectDeckFile(
        context: Context,
        file: File,
        isAsset: Boolean,
        assetName: String?
    ): DeckInfo? {
        return try {
            val reader = DatasetReader(file)
            val meta = reader.getMetadata()
            var target = meta["target_language"] ?: meta["target"]
            var native = meta["native_language"] ?: meta["native"]

            if (target.isNullOrBlank() || native.isNullOrBlank()) {
                val base = file.nameWithoutExtension
                val parts = base.split("_")
                if (parts.size >= 2) {
                    if (target.isNullOrBlank()) target = parts[0]
                    if (native.isNullOrBlank()) native = parts[1]
                } else {
                    if (target.isNullOrBlank()) target = base
                    if (native.isNullOrBlank()) native = "English"
                }
            }

            var cardCount = 0
            var vocabCount = 0
            try {
                reader.getVocabulary().size.also { vocabCount = it }
            } catch (_: Exception) {}

            try {
                val db = android.database.sqlite.SQLiteDatabase.openDatabase(
                    file.absolutePath,
                    null,
                    android.database.sqlite.SQLiteDatabase.OPEN_READONLY
                )
                val c1 = db.rawQuery("SELECT count(*) FROM cards", null)
                if (c1.moveToFirst()) cardCount = c1.getInt(0)
                c1.close()
                db.close()
            } catch (_: Exception) {}
            reader.close()

            val progressFile = getProgressFile(context, target)
            var stats: DeckStats? = null
            var savedDiff: Difficulty? = null
            var savedModes: List<Mode>? = null
            var savedAssume: Difficulty? = null

            if (progressFile.exists()) {
                try {
                    val tempReader = DatasetReader(file)
                    val tempDeck = tempReader.createDeckEngine()
                    tempDeck.load(progressFile)
                    stats = tempDeck.stats()
                    savedDiff = tempDeck.getDifficulty()
                    savedModes = tempDeck.getModes()
                    savedAssume = tempDeck.getAssumeKnown()
                    tempReader.close()
                } catch (_: Exception) {}
            }

            val title = when {
                isAsset && file.name.contains("sample", ignoreCase = true) ->
                    "${native.replaceFirstChar { it.uppercase() }} -> ${target.replaceFirstChar { it.uppercase() }} (Sample Deck)"
                else ->
                    "${native.replaceFirstChar { it.uppercase() }} -> ${target.replaceFirstChar { it.uppercase() }}"
            }

            DeckInfo(
                id = file.name,
                title = title,
                targetLanguage = target,
                nativeLanguage = native,
                file = file,
                assetName = assetName,
                isAsset = isAsset,
                cardCount = cardCount,
                vocabCount = vocabCount,
                savedStats = stats,
                savedDifficulty = savedDiff,
                savedModes = savedModes,
                savedAssumeKnown = savedAssume
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed inspecting deck file: ${file.name}", e)
            null
        }
    }

    fun prepareDeck(
        context: Context,
        deckInfo: DeckInfo,
        difficulty: Difficulty,
        modes: List<Mode>,
        assumeKnown: Difficulty?
    ): Pair<DatasetReader, DeckEngine> {
        val file = deckInfo.file ?: File(context.filesDir, deckInfo.assetName ?: "sample_deck.db")
        val (reader, deck) = loadDeckFromDb(file)
        loadProgress(context, deck)
        deck.setDifficulty(difficulty)
        deck.setModes(modes)
        deck.setAssumeKnown(assumeKnown)
        return Pair(reader, deck)
    }

    fun getProgressFile(context: Context, targetLang: String): File {
        val sanitizedLang = targetLang.replace(Regex("[^a-zA-Z0-9_-]"), "_").lowercase()
        val file = File(context.filesDir, "deck_${sanitizedLang}.json")
        if (!file.canonicalPath.startsWith(context.filesDir.canonicalPath)) {
            throw SecurityException("Path traversal attempt detected in target language identifier.")
        }
        return file
    }

    fun saveProgress(context: Context, deck: DeckEngine) {
        val file = getProgressFile(context, deck.targetLanguageCode)
        deck.save(file)
    }

    fun loadProgress(context: Context, deck: DeckEngine) {
        val file = getProgressFile(context, deck.targetLanguageCode)
        if (file.exists()) {
            deck.load(file)
        }
    }
}
