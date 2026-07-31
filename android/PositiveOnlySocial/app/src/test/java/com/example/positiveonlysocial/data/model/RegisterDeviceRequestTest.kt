package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Locks in the JSON body for device registration (issues #342/#343). The backend
 * reads `platform` and `token`; the @SerializedName mapping must produce exactly
 * those snake/lower-case keys or POST /devices/register/ 400s on invalid fields.
 */
class RegisterDeviceRequestTest {

    private val gson = Gson()

    @Test
    fun `serializes platform and token`() {
        val json = gson.toJson(RegisterDeviceRequest(platform = "android", token = "fcm-token-abc"))

        val obj = JsonParser.parseString(json).asJsonObject
        assertEquals("android", obj.get("platform").asString)
        assertEquals("fcm-token-abc", obj.get("token").asString)
        assertEquals(2, obj.keySet().size)
    }
}
