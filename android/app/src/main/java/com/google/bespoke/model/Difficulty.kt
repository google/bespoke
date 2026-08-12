package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

enum class Difficulty(val value: String) {
    @SerializedName("A1")
    A1("A1"),

    @SerializedName("A2")
    A2("A2"),

    @SerializedName("B1")
    B1("B1"),

    @SerializedName("B2")
    B2("B2"),

    @SerializedName("C1")
    C1("C1"),

    @SerializedName("C2")
    C2("C2");

    companion object {
        fun fromValue(v: String): Difficulty =
            entries.firstOrNull { it.value.equals(v, ignoreCase = true) } ?: A1
    }

    override fun toString(): String = value
}
