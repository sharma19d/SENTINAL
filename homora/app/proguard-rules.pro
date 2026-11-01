# kotlinx.serialization: keep generated serializers for the app's @Serializable classes.
-keepattributes *Annotation*, InnerClasses
-keepclassmembers @kotlinx.serialization.Serializable class com.charonsecurity.homora.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.charonsecurity.homora.**$$serializer { *; }
