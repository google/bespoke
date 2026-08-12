package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

data class UnitTag(
    @SerializedName("occurance")
    val occurance: String,

    @SerializedName("unit_id")
    val unit_id: String
)
