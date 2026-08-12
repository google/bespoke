package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

data class CardUsage(
    @SerializedName("time")
    val time: Double, // seconds since epoch

    @SerializedName("is_reported")
    val is_reported: Boolean = false
)
