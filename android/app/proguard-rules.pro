# ProGuard / R8 configuration for Google Bespoke Android

# Retain generic signatures, annotations, and inner classes for Gson
-keepattributes Signature
-keepattributes *Annotation*
-keepattributes EnclosingMethod
-keepattributes InnerClasses

# Keep Gson's TypeToken and subclasses
-keep class com.google.gson.reflect.TypeToken { *; }
-keep class * extends com.google.gson.reflect.TypeToken { *; }

# Retain serialized fields and models for Gson
-keep class com.google.bespoke.model.** { *; }
-keep class com.google.bespoke.data.** { *; }
-keep class com.google.bespoke.srs.** { *; }
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

