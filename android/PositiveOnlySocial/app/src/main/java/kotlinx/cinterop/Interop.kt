package kotlinx.cinterop

fun Any?.toKString(): String = this?.toString() ?: ""
