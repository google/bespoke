package com.google.bespoke.data

import android.content.Context

object ThemePreferences {
    private const val PREFS_NAME = "bespoke_theme_prefs"
    private const val KEY_DARK_MODE = "key_dark_mode"
    private const val KEY_LAST_DECK_ID = "key_last_deck_id"

    fun isDarkModeEnabled(context: Context, systemDark: Boolean): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_DARK_MODE, systemDark)
    }

    fun setDarkModeEnabled(context: Context, enabled: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_DARK_MODE, enabled).apply()
    }

    fun getLastSelectedDeckId(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_LAST_DECK_ID, null)
    }

    fun setLastSelectedDeckId(context: Context, deckId: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_LAST_DECK_ID, deckId).apply()
    }
}
