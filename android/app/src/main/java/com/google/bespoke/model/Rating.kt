package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

data class Rating(
    @SerializedName("mode")
    val mode: String,

    @SerializedName("time")
    val time: Double, // seconds since epoch

    @SerializedName("score")
    val score: Int // 0: Info/Blue, 1: Red, 2: Yellow, 3: Green
) {
    val modeEnum: Mode get() = Mode.fromValue(mode)
}
