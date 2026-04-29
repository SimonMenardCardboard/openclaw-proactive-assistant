import Foundation
import CoreLocation
import BackgroundTasks

/// Location tracker for Transmogrifier
/// Collects GPS data and syncs to webhook endpoint
class LocationTracker: NSObject, CLLocationManagerDelegate {
    static let shared = LocationTracker()
    
    private let locationManager = CLLocationManager()
    private let apiBaseURL: String
    private let authToken: String
    
    // Configuration
    private let syncInterval: TimeInterval = 300 // 5 minutes
    private let significantChangeOnly = true     // Battery-efficient
    
    // State
    private var lastSyncTime: Date?
    private var pendingLocations: [CLLocation] = []
    
    override init() {
        // Load config from UserDefaults or use defaults
        self.apiBaseURL = UserDefaults.standard.string(forKey: "TransmogrifierAPIURL") 
            ?? "https://user.transmogrifier.app"
        self.authToken = UserDefaults.standard.string(forKey: "TransmogrifierAuthToken")
            ?? ""
        
        super.init()
        
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        locationManager.allowsBackgroundLocationUpdates = true
        locationManager.pausesLocationUpdatesAutomatically = false
        locationManager.showsBackgroundLocationIndicator = false
    }
    
    // MARK: - Public API
    
    func requestPermissions() {
        locationManager.requestAlwaysAuthorization()
    }
    
    func startTracking() {
        guard authToken.isEmpty == false else {
            print("⚠️  No auth token configured")
            return
        }
        
        if significantChangeOnly {
            // Battery-efficient: only updates on significant location changes
            locationManager.startMonitoringSignificantLocationChanges()
        } else {
            // Continuous tracking (drains battery faster)
            locationManager.startUpdatingLocation()
        }
        
        print("✅ Location tracking started (significant changes: \(significantChangeOnly))")
        
        // Schedule background sync
        scheduleBackgroundSync()
    }
    
    func stopTracking() {
        if significantChangeOnly {
            locationManager.stopMonitoringSignificantLocationChanges()
        } else {
            locationManager.stopUpdatingLocation()
        }
        
        print("⏸️  Location tracking stopped")
    }
    
    func configure(apiURL: String, token: String) {
        UserDefaults.standard.set(apiURL, forKey: "TransmogrifierAPIURL")
        UserDefaults.standard.set(token, forKey: "TransmogrifierAuthToken")
        UserDefaults.standard.synchronize()
        
        print("✅ Location tracker configured")
        print("   API: \(apiURL)")
        print("   Token: \(token.prefix(10))...")
    }
    
    // MARK: - CLLocationManagerDelegate
    
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        
        print("📍 Location update: \(location.coordinate.latitude), \(location.coordinate.longitude)")
        
        // Add to pending queue
        pendingLocations.append(location)
        
        // Sync if enough time has passed
        if shouldSync() {
            syncLocations()
        }
    }
    
    func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) {
        switch status {
        case .notDetermined:
            print("📍 Location permission: Not determined")
        case .restricted:
            print("⚠️  Location permission: Restricted")
        case .denied:
            print("❌ Location permission: Denied")
        case .authorizedAlways:
            print("✅ Location permission: Always (optimal)")
        case .authorizedWhenInUse:
            print("⚠️  Location permission: When in use (limited)")
        @unknown default:
            print("⚠️  Location permission: Unknown")
        }
    }
    
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        print("❌ Location error: \(error.localizedDescription)")
    }
    
    // MARK: - Geofence Monitoring
    
    func monitorGeofence(placeId: Int, name: String, lat: Double, lon: Double, radius: Double) {
        let region = CLCircularRegion(
            center: CLLocationCoordinate2D(latitude: lat, longitude: lon),
            radius: radius,
            identifier: "\(placeId)"
        )
        
        region.notifyOnEntry = true
        region.notifyOnExit = true
        
        locationManager.startMonitoring(for: region)
        
        print("✅ Geofence added: \(name) (radius: \(radius)m)")
    }
    
    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        print("📍 Entered region: \(region.identifier)")
        
        // Send geofence event
        sendGeofenceEvent(placeId: region.identifier, event: "enter")
    }
    
    func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        print("📍 Exited region: \(region.identifier)")
        
        sendGeofenceEvent(placeId: region.identifier, event: "exit")
    }
    
    // MARK: - Sync Logic
    
    private func shouldSync() -> Bool {
        guard let lastSync = lastSyncTime else { return true }
        
        let elapsed = Date().timeIntervalSince(lastSync)
        return elapsed >= syncInterval
    }
    
    private func syncLocations() {
        guard pendingLocations.isEmpty == false else { return }
        
        print("🔄 Syncing \(pendingLocations.count) location(s)...")
        
        // Send each location to webhook
        for location in pendingLocations {
            sendLocationUpdate(location)
        }
        
        // Clear queue
        pendingLocations.removeAll()
        lastSyncTime = Date()
    }
    
    private func sendLocationUpdate(_ location: CLLocation) {
        let url = URL(string: "\(apiBaseURL)/api/location/update")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Get activity (if available)
        let activity = getActivityType()
        
        // Build payload
        let payload: [String: Any] = [
            "lat": location.coordinate.latitude,
            "lon": location.coordinate.longitude,
            "accuracy": location.horizontalAccuracy,
            "altitude": location.altitude,
            "speed": location.speed,
            "activity": activity,
            "timestamp": ISO8601DateFormatter().string(from: location.timestamp),
            "battery_level": getBatteryLevel()
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        } catch {
            print("❌ Failed to serialize payload: \(error)")
            return
        }
        
        // Send request
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("❌ Location sync failed: \(error.localizedDescription)")
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    print("✅ Location synced")
                    
                    // Parse response to check for current place
                    if let data = data,
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let currentPlace = json["current_place"] as? [String: Any],
                       let placeName = currentPlace["name"] as? String {
                        print("📍 Currently at: \(placeName)")
                    }
                } else {
                    print("⚠️  Location sync failed: HTTP \(httpResponse.statusCode)")
                }
            }
        }.resume()
    }
    
    private func sendGeofenceEvent(placeId: String, event: String) {
        let url = URL(string: "\(apiBaseURL)/api/location/geofence_event")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "place_id": placeId,
            "event": event,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        } catch {
            print("❌ Failed to serialize geofence payload: \(error)")
            return
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("❌ Geofence event failed: \(error)")
                return
            }
            
            print("✅ Geofence event sent: \(event)")
        }.resume()
    }
    
    // MARK: - Background Sync
    
    private func scheduleBackgroundSync() {
        // Register background task
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.transmogrifier.location.sync",
            using: nil
        ) { task in
            self.handleBackgroundSync(task: task as! BGProcessingTask)
        }
        
        // Schedule next sync
        let request = BGProcessingTaskRequest(identifier: "com.transmogrifier.location.sync")
        request.earliestBeginDate = Date(timeIntervalSinceNow: syncInterval)
        request.requiresNetworkConnectivity = true
        
        do {
            try BGTaskScheduler.shared.submit(request)
            print("✅ Background sync scheduled")
        } catch {
            print("❌ Failed to schedule background sync: \(error)")
        }
    }
    
    private func handleBackgroundSync(task: BGProcessingTask) {
        print("🔄 Background sync triggered")
        
        // Sync pending locations
        syncLocations()
        
        // Mark task complete
        task.setTaskCompleted(success: true)
        
        // Schedule next sync
        scheduleBackgroundSync()
    }
    
    // MARK: - Utilities
    
    private func getActivityType() -> String {
        // TODO: Use CoreMotion to detect activity
        // (walking, running, driving, stationary)
        return "unknown"
    }
    
    private func getBatteryLevel() -> Int {
        UIDevice.current.isBatteryMonitoringEnabled = true
        let level = UIDevice.current.batteryLevel
        return Int(level * 100)
    }
}
