package com.transmogrifier.location

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import androidx.core.app.ActivityCompat
import androidx.work.*
import com.google.android.gms.location.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.TimeUnit

/**
 * Location tracker for Transmogrifier
 * Collects GPS data and syncs to webhook endpoint
 */
class LocationTracker(private val context: Context) {
    
    private val fusedLocationClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)
    
    private val geofencingClient: GeofencingClient =
        LocationServices.getGeofencingClient(context)
    
    private val sharedPrefs = context.getSharedPreferences("TransmogrifierLocation", Context.MODE_PRIVATE)
    
    // Configuration
    private val apiBaseUrl: String
        get() = sharedPrefs.getString("apiUrl", "") ?: ""
    
    private val authToken: String
        get() = sharedPrefs.getString("authToken", "") ?: ""
    
    private val syncIntervalMinutes = 5L
    
    // Location callback
    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { location ->
                println("📍 Location update: ${location.latitude}, ${location.longitude}")
                syncLocation(location)
            }
        }
    }
    
    // MARK: - Public API
    
    fun configure(apiUrl: String, token: String) {
        sharedPrefs.edit()
            .putString("apiUrl", apiUrl)
            .putString("authToken", token)
            .apply()
        
        println("✅ Location tracker configured")
        println("   API: $apiUrl")
        println("   Token: ${token.take(10)}...")
    }
    
    fun startTracking() {
        if (authToken.isEmpty()) {
            println("⚠️  No auth token configured")
            return
        }
        
        if (!hasLocationPermission()) {
            println("❌ Location permission not granted")
            return
        }
        
        val locationRequest = LocationRequest.Builder(
            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            TimeUnit.MINUTES.toMillis(syncIntervalMinutes)
        ).apply {
            setMinUpdateIntervalMillis(TimeUnit.MINUTES.toMillis(1))
            setMaxUpdateDelayMillis(TimeUnit.MINUTES.toMillis(10))
        }.build()
        
        try {
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                Looper.getMainLooper()
            )
            
            println("✅ Location tracking started (interval: ${syncIntervalMinutes}min)")
            
            // Schedule background sync
            scheduleBackgroundSync()
        } catch (e: SecurityException) {
            println("❌ Location permission error: ${e.message}")
        }
    }
    
    fun stopTracking() {
        fusedLocationClient.removeLocationUpdates(locationCallback)
        println("⏸️  Location tracking stopped")
    }
    
    fun addGeofence(placeId: Int, name: String, lat: Double, lon: Double, radius: Double) {
        if (!hasLocationPermission()) {
            println("❌ Location permission required for geofences")
            return
        }
        
        val geofence = Geofence.Builder()
            .setRequestId(placeId.toString())
            .setCircularRegion(lat, lon, radius.toFloat())
            .setExpirationDuration(Geofence.NEVER_EXPIRE)
            .setTransitionTypes(
                Geofence.GEOFENCE_TRANSITION_ENTER or Geofence.GEOFENCE_TRANSITION_EXIT
            )
            .build()
        
        val geofencingRequest = GeofencingRequest.Builder()
            .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_ENTER)
            .addGeofence(geofence)
            .build()
        
        val pendingIntent = getGeofencePendingIntent()
        
        try {
            geofencingClient.addGeofences(geofencingRequest, pendingIntent)
            println("✅ Geofence added: $name (radius: ${radius}m)")
        } catch (e: SecurityException) {
            println("❌ Geofence permission error: ${e.message}")
        }
    }
    
    // MARK: - Private Methods
    
    private fun hasLocationPermission(): Boolean {
        return ActivityCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private fun syncLocation(location: Location) {
        CoroutineScope(Dispatchers.IO).launch {
            val client = OkHttpClient()
            
            val payload = JSONObject().apply {
                put("lat", location.latitude)
                put("lon", location.longitude)
                put("accuracy", location.accuracy)
                put("altitude", location.altitude)
                put("speed", location.speed)
                put("timestamp", Instant.now().toString())
                put("battery_level", getBatteryLevel())
            }
            
            val request = Request.Builder()
                .url("$apiBaseUrl/api/location/update")
                .addHeader("Authorization", "Bearer $authToken")
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()
            
            try {
                val response = client.newCall(request).execute()
                if (response.isSuccessful) {
                    println("✅ Location synced")
                    
                    // Check for current place
                    response.body?.string()?.let { body ->
                        val json = JSONObject(body)
                        if (json.has("current_place")) {
                            val place = json.getJSONObject("current_place")
                            val placeName = place.getString("name")
                            println("📍 Currently at: $placeName")
                        }
                    }
                } else {
                    println("⚠️  Location sync failed: HTTP ${response.code}")
                }
            } catch (e: Exception) {
                println("❌ Location sync error: ${e.message}")
            }
        }
    }
    
    private fun scheduleBackgroundSync() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        
        val syncRequest = PeriodicWorkRequestBuilder<LocationSyncWorker>(
            syncIntervalMinutes, TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .build()
        
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "location_sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
        
        println("✅ Background sync scheduled")
    }
    
    private fun getGeofencePendingIntent(): PendingIntent {
        val intent = Intent(context, GeofenceBroadcastReceiver::class.java)
        return PendingIntent.getBroadcast(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
        )
    }
    
    private fun getBatteryLevel(): Int {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as android.os.BatteryManager
        return batteryManager.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }
}

/**
 * Background worker for periodic location sync
 */
class LocationSyncWorker(
    context: Context,
    params: WorkerParameters
) : Worker(context, params) {
    
    override fun doWork(): Result {
        println("🔄 Background location sync triggered")
        
        // Get last location and sync
        val fusedLocationClient = LocationServices.getFusedLocationProviderClient(applicationContext)
        
        try {
            fusedLocationClient.lastLocation.addOnSuccessListener { location ->
                location?.let {
                    LocationTracker(applicationContext).syncLocation(it)
                }
            }
            
            return Result.success()
        } catch (e: SecurityException) {
            println("❌ Background sync failed: ${e.message}")
            return Result.failure()
        }
    }
}

/**
 * Broadcast receiver for geofence events
 */
class GeofenceBroadcastReceiver : android.content.BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val geofencingEvent = GeofencingEvent.fromIntent(intent)
        
        if (geofencingEvent == null) {
            println("❌ Geofence event is null")
            return
        }
        
        if (geofencingEvent.hasError()) {
            println("❌ Geofence error: ${geofencingEvent.errorCode}")
            return
        }
        
        val geofenceTransition = geofencingEvent.geofenceTransition
        
        when (geofenceTransition) {
            Geofence.GEOFENCE_TRANSITION_ENTER -> {
                geofencingEvent.triggeringGeofences?.forEach { geofence ->
                    println("📍 Entered geofence: ${geofence.requestId}")
                    sendGeofenceEvent(context, geofence.requestId, "enter")
                }
            }
            Geofence.GEOFENCE_TRANSITION_EXIT -> {
                geofencingEvent.triggeringGeofences?.forEach { geofence ->
                    println("📍 Exited geofence: ${geofence.requestId}")
                    sendGeofenceEvent(context, geofence.requestId, "exit")
                }
            }
        }
    }
    
    private fun sendGeofenceEvent(context: Context, placeId: String, event: String) {
        CoroutineScope(Dispatchers.IO).launch {
            val sharedPrefs = context.getSharedPreferences("TransmogrifierLocation", Context.MODE_PRIVATE)
            val apiUrl = sharedPrefs.getString("apiUrl", "") ?: ""
            val token = sharedPrefs.getString("authToken", "") ?: ""
            
            if (apiUrl.isEmpty() || token.isEmpty()) {
                println("⚠️  No configuration for geofence event")
                return@launch
            }
            
            val client = OkHttpClient()
            val payload = JSONObject().apply {
                put("place_id", placeId)
                put("event", event)
                put("timestamp", Instant.now().toString())
            }
            
            val request = Request.Builder()
                .url("$apiUrl/api/location/geofence_event")
                .addHeader("Authorization", "Bearer $token")
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()
            
            try {
                val response = client.newCall(request).execute()
                if (response.isSuccessful) {
                    println("✅ Geofence event sent: $event")
                }
            } catch (e: Exception) {
                println("❌ Geofence event error: ${e.message}")
            }
        }
    }
}
