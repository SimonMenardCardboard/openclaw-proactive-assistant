# Location Tracking & Geofencing Implementation Plan

**Goal:** Add GPS tracking + geofencing + pattern recognition to Transmogrifier  
**Integration:** V8 continuous pattern daemon  
**Timeline:** 25-35 hours  
**Target:** Pro tier ($25/mo)

---

## Overview

### What This Adds

**Location Intelligence:**
- Track user location (GPS/WiFi/Cell)
- Learn places (home, office, gym, etc.)
- Detect patterns (commute times, frequent locations)
- Geofence alerts (entering/leaving places)
- Context-aware recommendations

**Example Insights:**
- "You usually leave for office at 8:15 AM - want to block calendar 8:00-9:15?"
- "At gym (detected) - auto-reply: 'In workout, will respond after 7 PM'"
- "500+ miles from home - adjusting timezone for notifications"
- "You visit Starbucks before every client meeting - reminder to grab coffee"

---

## Architecture

```
┌─────────────────────────────────────────┐
│ Mobile Apps (iOS/Android)               │
│ - CoreLocation / FusedLocationProvider  │
│ - Background location updates           │
│ - Geofence monitoring                   │
└──────────────┬──────────────────────────┘
               │
               │ POST JSON (location events)
               ↓
┌─────────────────────────────────────────┐
│ User VM: Webhook Endpoint               │
│ POST /api/location/update               │
│ - Validates auth token                  │
│ - Stores in locations.db                │
└──────────────┬──────────────────────────┘
               │
               ↓ (stored in database)
┌─────────────────────────────────────────┐
│ Location Database (SQLite)              │
│ - locations table (GPS points)          │
│ - places table (learned locations)      │
│ - geofences table (monitored areas)     │
│ - patterns table (commute, routines)    │
└──────────────┬──────────────────────────┘
               │
               ↓ (queries every 5 min)
┌─────────────────────────────────────────┐
│ V8 Continuous Pattern Daemon            │
│ - Detects location patterns             │
│ - Learns places (home, office, gym)     │
│ - Generates context-aware insights      │
└──────────────┬──────────────────────────┘
               │
               ↓ (delivers insights)
┌─────────────────────────────────────────┐
│ Proactive Queue → Telegram              │
│ "At gym - auto-reply enabled"           │
└─────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Backend Infrastructure (8-10 hours)

#### Step 1.1: Location Database (3 hours)

**File:** `location_tracking/location_db.py`

**Schema:**
```sql
-- GPS points (raw data)
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    accuracy REAL,           -- meters
    altitude REAL,
    speed REAL,              -- m/s
    activity TEXT,           -- stationary, walking, driving, etc.
    battery_level INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_time (user_email, timestamp)
);

-- Learned places (auto-detected + user-defined)
CREATE TABLE places (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    name TEXT NOT NULL,      -- "Home", "Office", "Starbucks on Main"
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    radius REAL DEFAULT 100, -- meters
    detected_count INTEGER DEFAULT 0,
    last_visit TEXT,
    category TEXT,           -- home, work, gym, food, etc.
    auto_detected BOOLEAN DEFAULT 0,
    INDEX idx_user (user_email)
);

-- Geofences (active monitoring)
CREATE TABLE geofences (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    place_id INTEGER,
    enabled BOOLEAN DEFAULT 1,
    notify_enter BOOLEAN DEFAULT 1,
    notify_exit BOOLEAN DEFAULT 0,
    dwell_time_seconds INTEGER DEFAULT 300,  -- notify after 5 min
    FOREIGN KEY (place_id) REFERENCES places(id)
);

-- Location patterns (learned)
CREATE TABLE patterns (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    pattern_type TEXT NOT NULL,  -- commute, routine, travel
    from_place_id INTEGER,
    to_place_id INTEGER,
    typical_time TEXT,           -- "08:15:00"
    day_of_week INTEGER,         -- 0-6 (Mon-Sun)
    confidence REAL,
    last_detected TEXT,
    FOREIGN KEY (from_place_id) REFERENCES places(id),
    FOREIGN KEY (to_place_id) REFERENCES places(id)
);
```

**Implementation:**
```python
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2

class LocationDB:
    """Location tracking database with pattern learning"""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/location_tracking/locations.db'
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        # (Create tables as shown above)
    
    def record_location(
        self, 
        user_email: str,
        lat: float, 
        lon: float, 
        timestamp: Optional[str] = None,
        accuracy: Optional[float] = None,
        activity: Optional[str] = None
    ) -> int:
        """
        Record a location point.
        
        Returns: location_id
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO locations (user_email, timestamp, lat, lon, accuracy, activity)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_email, timestamp, lat, lon, accuracy, activity))
        
        location_id = cursor.lastrowid
        
        # Check if this location matches any known places
        self._check_place_detection(user_email, lat, lon)
        
        conn.commit()
        conn.close()
        
        return location_id
    
    def _check_place_detection(self, user_email: str, lat: float, lon: float):
        """Check if location is within any place's geofence"""
        places = self.get_places(user_email)
        
        for place in places:
            distance = self._haversine_distance(
                lat, lon, 
                place['lat'], place['lon']
            )
            
            if distance <= place['radius']:
                # User is at this place
                self._increment_place_visit(place['id'])
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS points in meters.
        
        Uses Haversine formula.
        """
        R = 6371000  # Earth radius in meters
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def get_current_place(self, user_email: str) -> Optional[Dict]:
        """
        Get user's current place based on most recent location.
        
        Returns: Place dict or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get most recent location
        cursor.execute('''
            SELECT lat, lon FROM locations
            WHERE user_email = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (user_email,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        lat, lon = result
        
        # Find matching place
        places = self.get_places(user_email)
        for place in places:
            distance = self._haversine_distance(lat, lon, place['lat'], place['lon'])
            if distance <= place['radius']:
                conn.close()
                return place
        
        conn.close()
        return None
    
    def learn_place(
        self,
        user_email: str,
        lat: float,
        lon: float,
        min_visits: int = 5,
        radius: float = 100
    ) -> Optional[int]:
        """
        Auto-detect a new place based on clustering.
        
        Returns: place_id if new place detected, else None
        """
        # Get recent locations near this point
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM locations
            WHERE user_email = ?
            AND timestamp > datetime('now', '-30 days')
        ''', (user_email,))
        
        nearby_count = 0
        # (Simplified - real implementation would cluster GPS points)
        
        if nearby_count >= min_visits:
            # Create new place
            return self.add_place(
                user_email=user_email,
                name=f"Detected Place {datetime.now().strftime('%Y%m%d')}",
                lat=lat,
                lon=lon,
                radius=radius,
                auto_detected=True
            )
        
        conn.close()
        return None
    
    def add_place(
        self,
        user_email: str,
        name: str,
        lat: float,
        lon: float,
        radius: float = 100,
        category: Optional[str] = None,
        auto_detected: bool = False
    ) -> int:
        """Add a place manually or via auto-detection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO places (user_email, name, lat, lon, radius, category, auto_detected)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_email, name, lat, lon, radius, category, auto_detected))
        
        place_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return place_id
    
    def get_places(self, user_email: str) -> List[Dict]:
        """Get all places for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM places
            WHERE user_email = ?
            ORDER BY detected_count DESC
        ''', (user_email,))
        
        places = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return places
    
    def detect_commute_pattern(self, user_email: str) -> Optional[Dict]:
        """
        Detect regular commute patterns.
        
        Returns: Pattern dict with from_place, to_place, typical_time
        """
        # Analyze location transitions over past 30 days
        # Identify regular movements between places
        # Calculate typical departure times
        
        # (Simplified implementation - full version would use ML clustering)
        return None
```

**Testing:**
```python
# test_location_db.py
db = LocationDB()

# Record locations
db.record_location('simon@email.com', 37.7749, -122.4194)  # San Francisco
db.record_location('simon@email.com', 37.7849, -122.4094)  # Different spot

# Add a place
home_id = db.add_place('simon@email.com', 'Home', 37.7749, -122.4194, radius=50)

# Check current place
current = db.get_current_place('simon@email.com')
print(f"Currently at: {current['name']}")
```

---

#### Step 1.2: Location Webhook Endpoint (2 hours)

**File:** `webhooks/location_webhook.py`

```python
#!/usr/bin/env python3
"""
Location Webhook Receiver

Receives GPS updates from mobile apps and stores in location database.

Endpoint: POST /api/location/update
Auth: Bearer token (user-specific)
Rate limit: 60 requests/minute per user
"""

from flask import Flask, request, jsonify
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent / 'location_tracking'))
from location_db import LocationDB

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize database
location_db = LocationDB()

# Simple auth (TODO: Use proper JWT tokens)
VALID_TOKENS = {
    'simon-token-123': 'simon@email.com'
}

@app.route('/api/location/update', methods=['POST'])
def update_location():
    """
    Receive location update from mobile app.
    
    Request body:
    {
        "lat": 37.7749,
        "lon": -122.4194,
        "accuracy": 10.5,
        "timestamp": "2026-04-29T14:30:00Z",
        "activity": "walking",
        "battery_level": 75
    }
    """
    # Verify auth
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid auth token'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = VALID_TOKENS.get(token)
    
    if not user_email:
        return jsonify({'error': 'Invalid token'}), 401
    
    # Parse request
    data = request.get_json()
    
    if not data or 'lat' not in data or 'lon' not in data:
        return jsonify({'error': 'Missing lat/lon'}), 400
    
    # Record location
    location_id = location_db.record_location(
        user_email=user_email,
        lat=data['lat'],
        lon=data['lon'],
        timestamp=data.get('timestamp'),
        accuracy=data.get('accuracy'),
        activity=data.get('activity')
    )
    
    # Check if user entered/left a place
    current_place = location_db.get_current_place(user_email)
    
    response = {
        'status': 'ok',
        'location_id': location_id
    }
    
    if current_place:
        response['current_place'] = {
            'id': current_place['id'],
            'name': current_place['name']
        }
    
    logging.info(f"Location updated for {user_email}: {data['lat']}, {data['lon']}")
    
    return jsonify(response), 200

@app.route('/api/location/places', methods=['GET'])
def get_places():
    """Get all places for authenticated user"""
    # Auth check (same as above)
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing auth'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = VALID_TOKENS.get(token)
    
    if not user_email:
        return jsonify({'error': 'Invalid token'}), 401
    
    places = location_db.get_places(user_email)
    
    return jsonify({'places': places}), 200

@app.route('/api/location/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=False)
```

**Deployment:**
```bash
# Start location webhook on user VM
nohup python3 webhooks/location_webhook.py \
  --port 5005 \
  > logs/location_webhook.log 2>&1 &

echo "✅ Location webhook started (port 5005)"
```

---

#### Step 1.3: Geofence Manager (3 hours)

**File:** `location_tracking/geofence_manager.py`

```python
#!/usr/bin/env python3
"""
Geofence Manager

Monitors geofence entry/exit events and triggers actions.

Actions:
- Notify user ("Entered: Home")
- Queue insight ("At gym - auto-reply enabled")
- Trigger automation ("Leaving office - disable work notifications")
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import sys

sys.path.insert(0, str(Path.home() / '.openclaw/workspace/integrations/intelligence'))
from proactive_queue import ProactiveQueue

class GeofenceManager:
    """Manage geofences and trigger actions"""
    
    def __init__(self, location_db_path: Optional[Path] = None):
        if location_db_path is None:
            location_db_path = Path.home() / '.openclaw/workspace/location_tracking/locations.db'
        
        self.db_path = location_db_path
        self.queue = ProactiveQueue()
        
        # Track last geofence state to detect transitions
        self.last_state = {}  # {user_email: {place_id: 'inside' or 'outside'}}
    
    def check_geofences(self, user_email: str):
        """
        Check all active geofences for a user.
        
        Detects entry/exit events and triggers actions.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user's current location
        cursor.execute('''
            SELECT lat, lon FROM locations
            WHERE user_email = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (user_email,))
        
        location = cursor.fetchone()
        if not location:
            conn.close()
            return
        
        lat, lon = location['lat'], location['lon']
        
        # Get active geofences
        cursor.execute('''
            SELECT g.*, p.name, p.lat, p.lon, p.radius
            FROM geofences g
            JOIN places p ON g.place_id = p.id
            WHERE g.user_email = ? AND g.enabled = 1
        ''', (user_email,))
        
        geofences = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Check each geofence
        for geofence in geofences:
            self._check_geofence(user_email, geofence, lat, lon)
    
    def _check_geofence(self, user_email: str, geofence: Dict, lat: float, lon: float):
        """Check a single geofence and trigger actions if needed"""
        from location_db import LocationDB
        
        db = LocationDB(self.db_path)
        distance = db._haversine_distance(lat, lon, geofence['lat'], geofence['lon'])
        
        inside = distance <= geofence['radius']
        place_id = geofence['place_id']
        
        # Get last state
        if user_email not in self.last_state:
            self.last_state[user_email] = {}
        
        last_inside = self.last_state[user_email].get(place_id, None)
        
        # Detect state change
        if inside and last_inside == False:
            # Entered geofence
            if geofence['notify_enter']:
                self._trigger_enter(user_email, geofence)
        
        elif not inside and last_inside == True:
            # Exited geofence
            if geofence['notify_exit']:
                self._trigger_exit(user_email, geofence)
        
        # Update state
        self.last_state[user_email][place_id] = inside
    
    def _trigger_enter(self, user_email: str, geofence: Dict):
        """Trigger actions when user enters a geofence"""
        place_name = geofence['name']
        
        # Queue notification
        self.queue.add(
            source='geofence-enter',
            message=f"📍 *Entered: {place_name}*",
            priority=2,
            metadata=json.dumps({
                'geofence_id': geofence['id'],
                'place_id': geofence['place_id'],
                'event': 'enter'
            })
        )
        
        # Trigger context-specific actions
        if 'gym' in place_name.lower():
            self.queue.add(
                source='geofence-context',
                message=f"🏋️ At gym - Auto-reply enabled: 'In workout, will respond after 7 PM'",
                priority=1
            )
        
        elif 'office' in place_name.lower():
            self.queue.add(
                source='geofence-context',
                message=f"💼 Arrived at office - Work notifications enabled",
                priority=2
            )
    
    def _trigger_exit(self, user_email: str, geofence: Dict):
        """Trigger actions when user exits a geofence"""
        place_name = geofence['name']
        
        self.queue.add(
            source='geofence-exit',
            message=f"📍 Left: {place_name}",
            priority=3,
            metadata=json.dumps({
                'geofence_id': geofence['id'],
                'place_id': geofence['place_id'],
                'event': 'exit'
            })
        )


# Background daemon that checks geofences
def geofence_monitor_daemon(interval_seconds: int = 60):
    """Run geofence monitoring continuously"""
    import time
    
    manager = GeofenceManager()
    
    # Get all users with geofences
    conn = sqlite3.connect(manager.db_path)
    cursor = conn.cursor()
    
    while True:
        cursor.execute('SELECT DISTINCT user_email FROM geofences WHERE enabled = 1')
        users = [row[0] for row in cursor.fetchall()]
        
        for user_email in users:
            manager.check_geofences(user_email)
        
        time.sleep(interval_seconds)
    
    conn.close()


if __name__ == '__main__':
    print("Starting geofence monitor daemon...")
    geofence_monitor_daemon(interval_seconds=60)
```

**Deployment:**
```bash
# Start geofence monitor
nohup python3 location_tracking/geofence_manager.py \
  > logs/geofence_monitor.log 2>&1 &

echo "✅ Geofence monitor started"
```

---

### Phase 2: Mobile Apps (12-15 hours)

#### Step 2.1: iOS Location Collection (6-7 hours)

**File:** `mobile_apps/ios/LocationTracker.swift`

```swift
import Foundation
import CoreLocation
import BackgroundTasks

class LocationTracker: NSObject, CLLocationManagerDelegate {
    static let shared = LocationTracker()
    
    private let locationManager = CLLocationManager()
    private let apiBaseURL = "https://simon.transmogrifier.app"
    private let authToken = "simon-token-123"  // TODO: Get from keychain
    
    override init() {
        super.init()
        
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        locationManager.allowsBackgroundLocationUpdates = true
        locationManager.pausesLocationUpdatesAutomatically = false
    }
    
    func requestPermissions() {
        locationManager.requestAlwaysAuthorization()
    }
    
    func startTracking() {
        locationManager.startUpdatingLocation()
        
        // Also monitor significant location changes (battery-efficient)
        locationManager.startMonitoringSignificantLocationChanges()
    }
    
    func stopTracking() {
        locationManager.stopUpdatingLocation()
        locationManager.stopMonitoringSignificantLocationChanges()
    }
    
    // CLLocationManagerDelegate
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        
        // Send to webhook
        sendLocationUpdate(location)
    }
    
    func sendLocationUpdate(_ location: CLLocation) {
        let url = URL(string: "\\(apiBaseURL)/api/location/update")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \\(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "lat": location.coordinate.latitude,
            "lon": location.coordinate.longitude,
            "accuracy": location.horizontalAccuracy,
            "altitude": location.altitude,
            "speed": location.speed,
            "timestamp": ISO8601DateFormatter().string(from: location.timestamp)
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Location update failed: \\(error)")
                return
            }
            
            print("Location update sent successfully")
        }.resume()
    }
    
    // Geofence monitoring
    func monitorGeofence(place: Place) {
        let region = CLCircularRegion(
            center: CLLocationCoordinate2D(latitude: place.lat, longitude: place.lon),
            radius: place.radius,
            identifier: "\\(place.id)"
        )
        
        region.notifyOnEntry = true
        region.notifyOnExit = true
        
        locationManager.startMonitoring(for: region)
    }
    
    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        print("Entered region: \\(region.identifier)")
        
        // Send geofence event
        sendGeofenceEvent(placeId: region.identifier, event: "enter")
    }
    
    func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        print("Exited region: \\(region.identifier)")
        
        sendGeofenceEvent(placeId: region.identifier, event: "exit")
    }
    
    func sendGeofenceEvent(placeId: String, event: String) {
        // Send notification to webhook
        // (Similar to sendLocationUpdate)
    }
}
```

**Info.plist additions:**
```xml
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>Transmogrifier uses your location to provide context-aware recommendations and productivity insights.</string>

<key>NSLocationWhenInUseUsageDescription</key>
<string>Transmogrifier uses your location for context-aware productivity insights.</string>

<key>UIBackgroundModes</key>
<array>
    <string>location</string>
    <string>fetch</string>
</array>
```

---

#### Step 2.2: Android Location Collection (6-8 hours)

**File:** `mobile_apps/android/LocationTracker.kt`

```kotlin
package com.transmogrifier.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import androidx.core.app.ActivityCompat
import com.google.android.gms.location.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.time.Instant

class LocationTracker(private val context: Context) {
    
    private val fusedLocationClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)
    
    private val geofencingClient: GeofencingClient =
        LocationServices.getGeofencingClient(context)
    
    private val apiBaseUrl = "https://simon.transmogrifier.app"
    private val authToken = "simon-token-123"  // TODO: Get from secure storage
    
    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { location ->
                sendLocationUpdate(location)
            }
        }
    }
    
    fun startTracking() {
        if (ActivityCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        
        val locationRequest = LocationRequest.Builder(
            Priority.PRIORITY_HIGH_ACCURACY,
            300000  // 5 minutes
        ).apply {
            setMinUpdateIntervalMillis(60000)  // 1 minute minimum
            setMaxUpdateDelayMillis(600000)    // 10 minutes maximum
        }.build()
        
        fusedLocationClient.requestLocationUpdates(
            locationRequest,
            locationCallback,
            Looper.getMainLooper()
        )
    }
    
    fun stopTracking() {
        fusedLocationClient.removeLocationUpdates(locationCallback)
    }
    
    private fun sendLocationUpdate(location: Location) {
        CoroutineScope(Dispatchers.IO).launch {
            val client = OkHttpClient()
            
            val payload = JSONObject().apply {
                put("lat", location.latitude)
                put("lon", location.longitude)
                put("accuracy", location.accuracy)
                put("altitude", location.altitude)
                put("speed", location.speed)
                put("timestamp", Instant.now().toString())
            }
            
            val request = Request.Builder()
                .url("$apiBaseUrl/api/location/update")
                .addHeader("Authorization", "Bearer $authToken")
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()
            
            try {
                val response = client.newCall(request).execute()
                if (response.isSuccessful) {
                    println("Location update sent successfully")
                } else {
                    println("Location update failed: ${response.code}")
                }
            } catch (e: Exception) {
                println("Location update error: ${e.message}")
            }
        }
    }
    
    fun addGeofence(place: Place) {
        val geofence = Geofence.Builder()
            .setRequestId(place.id.toString())
            .setCircularRegion(place.lat, place.lon, place.radius.toFloat())
            .setExpirationDuration(Geofence.NEVER_EXPIRE)
            .setTransitionTypes(Geofence.GEOFENCE_TRANSITION_ENTER or Geofence.GEOFENCE_TRANSITION_EXIT)
            .build()
        
        val geofencingRequest = GeofencingRequest.Builder()
            .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_ENTER)
            .addGeofence(geofence)
            .build()
        
        if (ActivityCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        
        geofencingClient.addGeofences(geofencingRequest, geofencePendingIntent)
    }
}

data class Place(
    val id: Int,
    val name: String,
    val lat: Double,
    val lon: Double,
    val radius: Double
)
```

---

### Phase 3: V8 Integration (5-8 hours)

#### Step 3.1: Add Location Pattern Detection to V8 (4-6 hours)

**File:** `v8_continuous_pattern_daemon.py` (enhancement)

```python
async def _check_location_patterns(self) -> List[Dict]:
    """Check for location-based patterns"""
    insights = []
    
    try:
        from location_tracking.location_db import LocationDB
        from location_tracking.geofence_manager import GeofenceManager
        
        location_db = LocationDB()
        geofence_mgr = GeofenceManager()
        
        # Get user's recent locations
        user_email = 'simon@email.com'  # TODO: Get from config
        
        # 1. Detect current place
        current_place = location_db.get_current_place(user_email)
        
        if current_place:
            # Check for context-specific insights
            if 'gym' in current_place['name'].lower():
                insights.append({
                    'pattern_id': f"location_gym_{current_place['id']}",
                    'pattern_type': 'location',
                    'message': f"🏋️ *At {current_place['name']}* - Auto-reply enabled for workouts",
                    'confidence': 0.95,
                    'priority': 1
                })
            
            elif 'office' in current_place['name'].lower():
                # Check if user usually arrives at this time
                from datetime import datetime
                current_hour = datetime.now().hour
                
                if current_hour >= 8 and current_hour <= 10:
                    insights.append({
                        'pattern_id': f"location_commute_{current_place['id']}",
                        'pattern_type': 'location',
                        'message': f"💼 Arrived at {current_place['name']} - on schedule",
                        'confidence': 0.90,
                        'priority': 2
                    })
        
        # 2. Detect commute patterns
        commute = location_db.detect_commute_pattern(user_email)
        
        if commute:
            insights.append({
                'pattern_id': f"commute_{commute['from_place_id']}_{commute['to_place_id']}",
                'pattern_type': 'commute',
                'message': f"🚗 *Commute Pattern Detected*\n\nYou usually leave {commute['from_place']} at {commute['typical_time']} for {commute['to_place']}.\n\nWant to auto-block calendar during commute?",
                'confidence': commute['confidence'],
                'priority': 2
            })
        
        # 3. Check geofences
        geofence_mgr.check_geofences(user_email)
    
    except ImportError:
        # Location tracking not available
        pass
    except Exception as e:
        print(f"    ⚠️  Location pattern check failed: {e}", flush=True)
    
    return insights
```

**Add to pattern check cycle:**
```python
async def _pattern_check_cycle(self):
    """Execute one pattern detection cycle."""
    now = datetime.now()
    print(f"[{now.isoformat()}] Pattern check starting...", flush=True)
    
    # 1. Check for email patterns
    email_insights = await self._check_email_patterns()
    
    # 2. Check for calendar patterns
    calendar_insights = await self._check_calendar_patterns()
    
    # 3. Check for workflow patterns
    workflow_insights = await self._check_workflow_patterns()
    
    # 4. Check for location patterns (NEW)
    location_insights = await self._check_location_patterns()
    
    # 5. Queue insights
    total_insights = len(email_insights) + len(calendar_insights) + len(workflow_insights) + len(location_insights)
    
    if total_insights > 0:
        print(f"  ✅ Found {total_insights} new insights", flush=True)
        
        for insight in email_insights + calendar_insights + workflow_insights + location_insights:
            if insight['pattern_id'] not in self.detected_patterns:
                self.queue.add(
                    source='v8-pattern-learning',
                    message=insight['message'],
                    priority=insight.get('priority', 2),
                    metadata=json.dumps({
                        'pattern_id': insight['pattern_id'],
                        'pattern_type': insight['pattern_type'],
                        'confidence': insight['confidence']
                    })
                )
                self.detected_patterns.add(insight['pattern_id'])
                print(f"    📊 {insight['pattern_type']}: {insight['pattern_id']}", flush=True)
```

---

#### Step 3.2: Location-Aware Recommendations (2 hours)

**Example patterns V8 can detect:**

**1. Commute Time Blocking**
```python
Pattern detected:
- Leave home at 8:15 AM ±10 min (Mon-Fri)
- Arrive office at 9:05 AM ±15 min
- Confidence: 0.92

Recommendation:
"You commute 8:15-9:15 AM weekdays. Want to auto-block calendar during this time?"

User action:
- Approve → Auto-create recurring blocker
- Deny → Never ask again
```

**2. Workout Auto-Reply**
```python
Pattern detected:
- At gym 6:00-7:00 PM (Mon/Wed/Fri)
- Confidence: 0.88

Recommendation:
"At gym - Auto-reply enabled: 'In workout, will respond after 7 PM'"

Auto-execution:
- Gmail: Set vacation responder
- Slack: Set status "🏋️ At gym"
- Calendar: Mark as busy
```

**3. Travel Detection**
```python
Pattern detected:
- 500+ miles from home
- Location: New York (usually SF)
- Confidence: 0.99

Recommendation:
"Detected travel to New York. Actions taken:
- Adjusted timezone (ET not PT)
- Paused local appointment reminders
- Added 'Traveling' note to calendar"
```

**4. Pre-Meeting Ritual**
```python
Pattern detected:
- Visit Starbucks before client meetings (80% of time)
- Average: 15 min before meeting

Recommendation:
"Client meeting in 30 min. You usually stop at Starbucks first - reminder to leave now?"
```

---

## Testing & Validation (2-3 hours)

### Test Plan

**1. Location Recording**
```bash
# Send test location
curl -X POST http://localhost:5005/api/location/update \
  -H "Authorization: Bearer simon-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 37.7749,
    "lon": -122.4194,
    "accuracy": 10,
    "timestamp": "2026-04-29T14:30:00Z"
  }'

# Check database
sqlite3 ~/.openclaw/workspace/location_tracking/locations.db \
  "SELECT * FROM locations ORDER BY timestamp DESC LIMIT 5;"
```

**2. Place Detection**
```bash
# Add a place
sqlite3 locations.db << 'SQL'
INSERT INTO places (user_email, name, lat, lon, radius) 
VALUES ('simon@email.com', 'Home', 37.7749, -122.4194, 50);
SQL

# Send location near home
# Should detect "At Home"
```

**3. Geofence Triggers**
```bash
# Send location entering gym
curl -X POST http://localhost:5005/api/location/update \
  -H "Authorization: Bearer simon-token-123" \
  -d '{"lat": 37.7850, "lon": -122.4100}'

# Check queue
sqlite3 proactive_queue.db \
  "SELECT message FROM queue WHERE source='geofence-enter' ORDER BY created_at DESC LIMIT 1;"

# Expected: "Entered: Gym"
```

**4. V8 Pattern Detection**
```bash
# Wait for V8 to run (5 min interval)
tail -f ~/.openclaw/workspace/logs/v8_continuous.log

# Expected:
# "Found 1 new insights"
# "location: location_gym_1"
```

---

## Deployment (1-2 hours)

### Production Checklist

**Backend (User VM):**
- [ ] Location database created
- [ ] Location webhook running (port 5005)
- [ ] Geofence monitor daemon running
- [ ] V8 continuous daemon updated
- [ ] Firewall allows port 5005
- [ ] SSL certificate configured

**Mobile Apps:**
- [ ] iOS app built and submitted to TestFlight
- [ ] Android app built and submitted to Google Play
- [ ] OAuth tokens configured
- [ ] Background location permission granted
- [ ] Geofences registered

**Testing:**
- [ ] Location updates received
- [ ] Places detected correctly
- [ ] Geofence events trigger
- [ ] V8 generates location insights
- [ ] Insights delivered to Telegram

---

## Privacy & Compliance

### Privacy Considerations

**1. User Consent**
- Explicit opt-in required
- Clear explanation of what's collected
- Easy opt-out option

**2. Data Minimization**
- Only collect GPS when needed (not continuous)
- Use significant location changes (battery-efficient)
- Delete old location data (>90 days)

**3. Data Security**
- Stored on user's private VM only
- Encrypted in transit (HTTPS)
- No third-party sharing
- User can view/delete all data

**4. Transparency**
- Show user map of tracked locations
- Show learned places
- Show active geofences
- Export all location data

### Privacy Policy Addition

```markdown
## Location Data

Transmogrifier Pro collects location data to provide context-aware productivity insights.

**What we collect:**
- GPS coordinates (latitude/longitude)
- Timestamp
- Location accuracy

**How we use it:**
- Detect places you frequently visit (home, office, gym)
- Learn commute patterns
- Provide context-aware recommendations
- Enable geofence-based automations

**Your data:**
- Stored on your private server only
- Never shared with third parties
- You can view, export, or delete anytime
- You can disable location tracking anytime

**Battery impact:**
- Uses "significant location changes" (Apple/Google battery-efficient APIs)
- Not continuous GPS tracking
- Typical battery impact: <5% per day
```

---

## Effort Summary

| Phase | Task | Hours |
|-------|------|-------|
| **1.1** | Location database | 3 |
| **1.2** | Webhook endpoint | 2 |
| **1.3** | Geofence manager | 3 |
| **2.1** | iOS location collection | 7 |
| **2.2** | Android location collection | 7 |
| **3.1** | V8 pattern detection | 5 |
| **3.2** | Location recommendations | 2 |
| **Testing** | End-to-end validation | 2 |
| **Deployment** | Production setup | 2 |
| **Total** | | **33 hours** |

---

## Timeline

**Week 1 (Backend):**
- Days 1-2: Location database + webhook
- Days 3-4: Geofence manager + testing
- Day 5: V8 integration

**Week 2 (Mobile):**
- Days 1-3: iOS app
- Days 4-6: Android app  
- Day 7: Testing + deployment

**Total: 2 weeks (~33 hours)**

---

## ROI Analysis

**Development cost:** 33 hours @ $150/hr = $4,950

**Revenue impact:**
- Basic tier: $15/mo
- Pro tier (with location): $25/mo
- **Upsell: $10/mo per user**

**Break-even:** 495 user-months = 50 users for 10 months

**Target:** 100 Pro tier users = $1,000/mo additional revenue

**Payback:** ~5 months

---

## Next Steps

1. **Decide:** Build location tracking now or defer to Q3 2026?
2. **If now:** Start with Phase 1 (backend infrastructure)
3. **If later:** Ship Basic tier, validate market, build based on user demand

**Recommendation:** Defer until 50+ Basic tier users ask for it. Don't build features before proving core value works.
