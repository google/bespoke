# ProGuard / R8 configuration for Google Bespoke Android

# Retain serialized fields and models for Gson
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

-keep class com.google.bespoke.model.** { *; }
-keep class com.google.bespoke.data.** { *; }
-keep class com.google.bespoke.srs.** { *; }
