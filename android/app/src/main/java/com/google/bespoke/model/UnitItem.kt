package com.google.bespoke.model

interface UnitItem {
    fun id(): String
    fun name(): String
    fun definition(): String
    fun difficulty(): Difficulty
}

data class WordUnit(
    val word: String,
    val diff: Difficulty
) : UnitItem {
    override fun id(): String = word
    override fun name(): String = word
    override fun definition(): String = word
    override fun difficulty(): Difficulty = diff

    override fun toString(): String = word
}

data class DictionaryUnit(
    val wordName: String,
    val defText: String,
    val diff: Difficulty
) : UnitItem {
    override fun id(): String = "$wordName - $defText"
    override fun name(): String = wordName
    override fun definition(): String = defText
    override fun difficulty(): Difficulty = diff

    override fun toString(): String = id()
}
