package com.google.bespoke.model

import java.io.File

data class DeckInfo(
    val id: String,
    val title: String,
    val targetLanguage: String,
    val nativeLanguage: String,
    val file: File?,
    val assetName: String? = null,
    val isAsset: Boolean = false,
    val cardCount: Int = 0,
    val vocabCount: Int = 0,
    val savedStats: DeckStats? = null,
    val savedDifficulty: Difficulty? = null,
    val savedModes: List<Mode>? = null,
    val savedAssumeKnown: Difficulty? = null
)
