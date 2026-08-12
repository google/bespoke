package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

enum class Mode(val value: String) {
    @SerializedName("listen")
    LISTEN("listen"),

    @SerializedName("speak")
    SPEAK("speak"),

    @SerializedName("read")
    READ("read"),

    @SerializedName("write")
    WRITE("write");

    companion object {
        fun fromValue(v: String): Mode =
            entries.firstOrNull { it.value.equals(v, ignoreCase = true) } ?: LISTEN
    }

    override fun toString(): String = value
}
