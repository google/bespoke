package com.google.bespoke.model

import com.google.gson.annotations.SerializedName

data class Card(
    @SerializedName("id")
    val id: String,

    @SerializedName("sentence")
    val sentence: String,

    @SerializedName("native_sentence")
    val native_sentence: String,

    @SerializedName("audio_filename")
    val audio_filename: String,

    @SerializedName("slow_audio_filename")
    val slow_audio_filename: String,

    @SerializedName("native_audio_filename")
    val native_audio_filename: String,

    @SerializedName("phonetic")
    val phonetic: String? = null,

    @SerializedName("unit_tags")
    val unit_tags: List<UnitTag> = emptyList(),

    @SerializedName("notes")
    val notes: List<String> = emptyList()
) {
    fun unitIds(): List<String> =
        unit_tags.mapNotNull { if (it.unit_id.isNotEmpty()) it.unit_id else null }.distinct()

    fun splitIntoParts(): List<UnitTag> {
        val parts = mutableListOf<UnitTag>()
        var sentenceIndex = 0
        for (tag in unit_tags) {
            val startIdx = sentence.indexOf(tag.occurance, sentenceIndex)
            if (startIdx >= 0) {
                if (startIdx > sentenceIndex) {
                    parts.add(
                        UnitTag(
                            occurance = sentence.substring(sentenceIndex, startIdx),
                            unit_id = ""
                        )
                    )
                }
                parts.add(tag)
                sentenceIndex = startIdx + tag.occurance.length
            }
        }
        if (sentenceIndex < sentence.length) {
            parts.add(
                UnitTag(
                    occurance = sentence.substring(sentenceIndex),
                    unit_id = ""
                )
            )
        }
        return parts
    }
}
