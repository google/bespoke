package com.google.bespoke.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.FileUpload
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.bespoke.R
import com.google.bespoke.data.ImportResult
import com.google.bespoke.data.ThemePreferences
import com.google.bespoke.model.DeckInfo
import com.google.bespoke.model.Difficulty
import com.google.bespoke.model.Mode
import com.google.bespoke.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StartScreen(
    availableDecks: List<DeckInfo>,
    onStartDeck: (deckInfo: DeckInfo, difficulty: Difficulty, modes: List<Mode>, assumeKnown: Difficulty?) -> Unit,
    isDarkMode: Boolean = false,
    onToggleDarkMode: ((Boolean) -> Unit)? = null,
    onImportDeck: (suspend (Uri) -> ImportResult)? = null,
    isLoading: Boolean = false,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val isDark = isDarkTheme()
    val headerColor = if (isDark) TextReadableDark else TextReadableLight
    val cardBg = if (isDark) CardBgDark else CardBgLight

    // State for selected deck (auto-selects last used deck if present)
    val initialDeckIndex = remember(availableDecks) {
        val lastId = ThemePreferences.getLastSelectedDeckId(context)
        if (lastId != null) {
            val idx = availableDecks.indexOfFirst { it.id == lastId }
            if (idx >= 0) idx else 0
        } else 0
    }
    var selectedDeckIndex by remember { mutableIntStateOf(initialDeckIndex) }
    val currentDeck = availableDecks.getOrNull(selectedDeckIndex) ?: availableDecks.firstOrNull()

    var selectedDifficulty by remember {
        mutableStateOf(currentDeck?.savedDifficulty ?: Difficulty.A1)
    }

    var listenMode by remember {
        mutableStateOf(currentDeck?.savedModes?.contains(Mode.LISTEN) ?: true)
    }
    var speakMode by remember {
        mutableStateOf(currentDeck?.savedModes?.contains(Mode.SPEAK) ?: true)
    }
    var readMode by remember {
        mutableStateOf(currentDeck?.savedModes?.contains(Mode.READ) ?: false)
    }
    var writeMode by remember {
        mutableStateOf(currentDeck?.savedModes?.contains(Mode.WRITE) ?: false)
    }

    var selectedAssumeKnown by remember {
        mutableStateOf<Difficulty?>(currentDeck?.savedAssumeKnown)
    }

    // Automatically synchronize mode and difficulty when selected deck changes
    LaunchedEffect(currentDeck) {
        currentDeck?.let { deck ->
            selectedDifficulty = deck.savedDifficulty ?: Difficulty.A1
            listenMode = deck.savedModes?.contains(Mode.LISTEN) ?: true
            speakMode = deck.savedModes?.contains(Mode.SPEAK) ?: true
            readMode = deck.savedModes?.contains(Mode.READ) ?: false
            writeMode = deck.savedModes?.contains(Mode.WRITE) ?: false
            selectedAssumeKnown = deck.savedAssumeKnown
            ThemePreferences.setLastSelectedDeckId(context, deck.id)
        }
    }

    var deckDropdownExpanded by remember { mutableStateOf(false) }
    var assumeDropdownExpanded by remember { mutableStateOf(false) }
    var isImporting by remember { mutableStateOf(false) }
    var importStatusMessage by remember { mutableStateOf<String?>(null) }

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null && onImportDeck != null) {
            isImporting = true
            importStatusMessage = "Importing dataset..."
            coroutineScope.launch {
                val result = withContext(Dispatchers.IO) {
                    onImportDeck(uri)
                }
                isImporting = false
                when (result) {
                    is ImportResult.Success -> {
                        val imported = result.deckInfo
                        val idx = availableDecks.indexOfFirst { it.id == imported.id }
                        if (idx >= 0) {
                            selectedDeckIndex = idx
                        }
                        importStatusMessage = "Imported deck: ${imported.title}"
                        Toast.makeText(context, "Imported deck: ${imported.title}", Toast.LENGTH_SHORT).show()
                    }
                    is ImportResult.ProgressSuccess -> {
                        val lang = result.targetLanguage.replaceFirstChar { it.uppercase() }
                        importStatusMessage = "Imported progress for $lang!"
                        Toast.makeText(context, "Imported progress for $lang", Toast.LENGTH_SHORT).show()
                    }
                    is ImportResult.Failure -> {
                        importStatusMessage = result.message
                        Toast.makeText(context, result.message, Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    var showLogsDialog by remember { mutableStateOf(false) }

    if (showLogsDialog) {
        val internal = File(context.filesDir, "crash.log")
        val ext = context.getExternalFilesDir(null)?.let { File(it, "crash.log") }
        var logContent by remember {
            val content = when {
                internal.exists() -> internal.readText(Charsets.UTF_8)
                ext?.exists() == true -> ext.readText(Charsets.UTF_8)
                else -> "No crash logs recorded. System is operating normally."
            }
            mutableStateOf(content)
        }

        AlertDialog(
            onDismissRequest = { showLogsDialog = false },
            title = { Text("Diagnostics & Crash Logs") },
            text = {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 320.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        text = logContent,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                        val clip = ClipData.newPlainText("Bespoke Logs", logContent)
                        clipboard?.setPrimaryClip(clip)
                        Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                    }
                ) {
                    Text("Copy")
                }
            },
            dismissButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(
                        onClick = {
                            try {
                                internal.delete()
                                ext?.delete()
                                logContent = "Logs cleared."
                            } catch (_: Exception) {}
                        }
                    ) {
                        Text("Clear")
                    }
                    TextButton(onClick = { showLogsDialog = false }) {
                        Text("Close")
                    }
                }
            }
        )
    }

    Scaffold(
        modifier = modifier
            .fillMaxSize()
            .testTag("StartScreen"),
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // App Title Header (Rounded pill icon, Logs button, Dark Mode toggle switch)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.testTag("AppTitleRow")
                ) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.White)
                            .border(
                                1.dp,
                                if (isDark) Color(0xFF3F3F46) else Color(0xFFE5E7EB),
                                RoundedCornerShape(8.dp)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_bespoke_icon),
                            contentDescription = "Bespoke Icon",
                            modifier = Modifier.size(28.dp)
                        )
                    }
                    Text(
                        text = "Bespoke",
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Light,
                        color = headerColor,
                        modifier = Modifier.testTag("AppTitle")
                    )
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    IconButton(
                        onClick = { showLogsDialog = true },
                        modifier = Modifier.size(36.dp).testTag("LogsButton")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Diagnostics and Logs",
                            tint = if (isDark) Color(0xFF9CA3AF) else Color(0xFF4B5563)
                        )
                    }

                    if (onToggleDarkMode != null) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            modifier = Modifier.testTag("DarkModeToggleRow")
                        ) {
                            Icon(
                                imageVector = if (isDarkMode) Icons.Default.DarkMode else Icons.Default.LightMode,
                                contentDescription = "Toggle Dark Mode",
                                modifier = Modifier.size(18.dp),
                                tint = if (isDark) Color(0xFF9CA3AF) else Color(0xFF4B5563)
                            )
                            Switch(
                                checked = isDarkMode,
                                onCheckedChange = { onToggleDarkMode(it) },
                                modifier = Modifier.testTag("DarkModeSwitch")
                            )
                        }
                    }
                }
            }

            // 1. Deck Selection Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("DeckSelectionCard"),
                colors = CardDefaults.cardColors(containerColor = cardBg),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        text = "Language Deck",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    if (availableDecks.isNotEmpty() && currentDeck != null) {
                        ExposedDropdownMenuBox(
                            expanded = deckDropdownExpanded,
                            onExpandedChange = { deckDropdownExpanded = !deckDropdownExpanded },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            OutlinedTextField(
                                value = currentDeck.title,
                                onValueChange = {},
                                readOnly = true,
                                label = { Text("Selected Deck") },
                                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = deckDropdownExpanded) },
                                modifier = Modifier
                                    .menuAnchor()
                                    .fillMaxWidth()
                                    .testTag("DeckSelectorTextField")
                            )
                            ExposedDropdownMenu(
                                expanded = deckDropdownExpanded,
                                onDismissRequest = { deckDropdownExpanded = false }
                            ) {
                                availableDecks.forEachIndexed { index, deckInfo ->
                                    DropdownMenuItem(
                                        text = {
                                            Column {
                                                Text(deckInfo.title, fontWeight = FontWeight.Medium)
                                                Text(
                                                    "${deckInfo.cardCount} cards • ${deckInfo.vocabCount} words",
                                                    fontSize = 12.sp,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                                )
                                            }
                                        },
                                        onClick = {
                                            selectedDeckIndex = index
                                            deckDropdownExpanded = false
                                        },
                                        modifier = Modifier.testTag("DeckOption_$index")
                                    )
                                }
                            }
                        }
                    } else {
                        Text(
                            text = "No database decks found. Import a .db file to begin.",
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.error
                        )
                    }

                    // Import Button & Status
                    if (onImportDeck != null) {
                        OutlinedButton(
                            onClick = {
                                filePickerLauncher.launch(arrayOf("*/*"))
                            },
                            enabled = !isImporting,
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("ImportDeckButton"),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            if (isImporting) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Importing...")
                            } else {
                                Icon(
                                    imageVector = Icons.Default.FileUpload,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Import")
                            }
                        }

                        if (importStatusMessage != null && !isImporting) {
                            Text(
                                text = importStatusMessage!!,
                                fontSize = 12.sp,
                                color = if (importStatusMessage!!.startsWith("Imported")) PrimaryBlue else MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("ImportStatusText")
                            )
                        }
                    }
                }
            }

            // 2. Difficulty Selection Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("DifficultyCard"),
                colors = CardDefaults.cardColors(containerColor = cardBg),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        text = "Target Difficulty",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Difficulty.entries.forEach { diff ->
                            val isSelected = selectedDifficulty == diff
                            FilterChip(
                                selected = isSelected,
                                onClick = { selectedDifficulty = diff },
                                label = {
                                    Text(
                                        diff.value,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        maxLines = 1,
                                        softWrap = false
                                    )
                                },
                                leadingIcon = if (isSelected) {
                                    { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                                } else null,
                                modifier = Modifier.testTag("DifficultyChip_${diff.value}")
                            )
                        }
                    }
                }
            }

            // 3. Compact Learning Modes Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("ModesCard"),
                colors = CardDefaults.cardColors(containerColor = cardBg),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        text = "Learning Modes",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        FilterChip(
                            selected = listenMode,
                            onClick = { listenMode = !listenMode },
                            label = { Text("Listen", maxLines = 1, softWrap = false) },
                            leadingIcon = if (listenMode) {
                                { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                            } else null,
                            modifier = Modifier.testTag("ModeChip_Listen")
                        )

                        FilterChip(
                            selected = speakMode,
                            onClick = { speakMode = !speakMode },
                            label = { Text("Speak", maxLines = 1, softWrap = false) },
                            leadingIcon = if (speakMode) {
                                { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                            } else null,
                            modifier = Modifier.testTag("ModeChip_Speak")
                        )

                        FilterChip(
                            selected = readMode,
                            onClick = { readMode = !readMode },
                            label = { Text("Read", maxLines = 1, softWrap = false) },
                            leadingIcon = if (readMode) {
                                { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                            } else null,
                            modifier = Modifier.testTag("ModeChip_Read")
                        )

                        FilterChip(
                            selected = writeMode,
                            onClick = { writeMode = !writeMode },
                            label = { Text("Write", maxLines = 1, softWrap = false) },
                            leadingIcon = if (writeMode) {
                                { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                            } else null,
                            modifier = Modifier.testTag("ModeChip_Write")
                        )
                    }
                }
            }

            // 4. Assume Known Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("AssumeKnownCard"),
                colors = CardDefaults.cardColors(containerColor = cardBg),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = "Assume Known",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    ExposedDropdownMenuBox(
                        expanded = assumeDropdownExpanded,
                        onExpandedChange = { assumeDropdownExpanded = !assumeDropdownExpanded },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        OutlinedTextField(
                            value = selectedAssumeKnown?.let { "Up to ${it.value}" } ?: "None",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Word Level") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = assumeDropdownExpanded) },
                            modifier = Modifier
                                .menuAnchor()
                                .fillMaxWidth()
                                .testTag("AssumeKnownTextField")
                        )
                        ExposedDropdownMenu(
                            expanded = assumeDropdownExpanded,
                            onDismissRequest = { assumeDropdownExpanded = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("None") },
                                onClick = {
                                    selectedAssumeKnown = null
                                    assumeDropdownExpanded = false
                                },
                                modifier = Modifier.testTag("AssumeKnownOption_None")
                            )
                            Difficulty.entries.filter { it != Difficulty.C2 }.forEach { diff ->
                                DropdownMenuItem(
                                    text = { Text("Up to ${diff.value}") },
                                    onClick = {
                                        selectedAssumeKnown = diff
                                        assumeDropdownExpanded = false
                                    },
                                    modifier = Modifier.testTag("AssumeKnownOption_${diff.value}")
                                )
                            }
                        }
                    }
                }
            }

            // 5. Start Learning Button
            val activeModes = buildList {
                if (listenMode) add(Mode.LISTEN)
                if (speakMode) add(Mode.SPEAK)
                if (readMode) add(Mode.READ)
                if (writeMode) add(Mode.WRITE)
            }
            val canStart = currentDeck != null && activeModes.isNotEmpty()

            Button(
                onClick = {
                    if (currentDeck != null && canStart && !isLoading) {
                        onStartDeck(currentDeck, selectedDifficulty, activeModes, selectedAssumeKnown)
                    }
                },
                enabled = canStart && !isLoading,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp)
                    .testTag("StartLearningButton"),
                shape = RoundedCornerShape(12.dp)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        strokeWidth = 2.5.dp,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "Loading Deck...",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold
                    )
                } else {
                    Text(
                        text = "Start Learning",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}
