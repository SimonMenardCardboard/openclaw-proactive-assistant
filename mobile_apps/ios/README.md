# Transmogrifier iOS App - Location Tracking

GPS tracking app for Transmogrifier Pro tier.

---

## Features

- **Background location tracking** (battery-efficient)
- **Significant location changes** (not continuous GPS)
- **Geofence monitoring** (enter/exit detection)
- **Auto-sync to webhook** (every 5 minutes)
- **Privacy-focused** (data stays on your VM)

---

## Setup (Xcode)

### 1. Create New Project

```
Xcode → File → New → Project
- iOS App
- Product Name: Transmogrifier
- Interface: SwiftUI
- Language: Swift
```

### 2. Add Files

Copy these files to your Xcode project:
- `LocationTracker.swift`
- `TransmogrifierApp.swift`
- `Info.plist` (merge with existing)

### 3. Configure Capabilities

**Targets → Transmogrifier → Signing & Capabilities:**

Add:
- Background Modes
  - ✅ Location updates
  - ✅ Background fetch
  - ✅ Background processing

### 4. Configure Info.plist

Already included in `Info.plist` file:
- Location permissions (Always + When In Use)
- Background modes
- Background task identifiers

### 5. Test on Device

**You MUST test on real device** (location doesn't work in simulator)

1. Connect iPhone via USB
2. Select device in Xcode
3. Run app (Cmd+R)
4. Grant location permission ("Always Allow")
5. Configure API URL + token
6. Start tracking

---

## Configuration

### API URL

Production: `https://simon.transmogrifier.app`  
Development: `http://192.168.1.101:5005` (local testing)

### Auth Token

Get from user's account settings or onboarding flow.

Example: `simon-location-token-abc123`

---

## How It Works

### 1. Location Collection

Uses `CoreLocation` framework:
- `CLLocationManager` for GPS
- `startMonitoringSignificantLocationChanges()` (battery-efficient)
- Only updates when user moves significantly (~500m)

**Battery impact:** <5% per day (Apple-optimized)

### 2. Geofence Monitoring

- Up to 20 geofences per app (iOS limit)
- Entry/exit events trigger immediately
- Works even when app is terminated

### 3. Background Sync

- Collects GPS points in queue
- Syncs every 5 minutes (configurable)
- Uses Background Tasks API (iOS 13+)

### 4. Data Flow

```
iPhone GPS → LocationTracker
↓
Pending queue (in-memory)
↓
Every 5 min: POST to /api/location/update
↓
Webhook → location_db.py
↓
V8 pattern detection
↓
Insights delivered
```

---

## Privacy

### What's Collected

- GPS coordinates (lat/lon)
- Accuracy (meters)
- Altitude, speed
- Timestamp
- Battery level

### What's NOT Collected

- Names of nearby places
- Address reverse geocoding
- Photos, contacts, messages
- Other app data

### Where Data Goes

- Your private VM only (`https://you.transmogrifier.app`)
- Never shared with Apple
- Never shared with Transmogrifier company
- Never shared with third parties

### User Controls

- View all tracked locations
- Pause tracking anytime
- Delete all location data
- Export data (JSON)

---

## Testing

### Local Testing

1. Start local webhook:
```bash
python3 webhooks/location_webhook.py --port 5005
```

2. Configure app:
- API URL: `http://192.168.1.101:5005`
- Token: `test-token`

3. Walk around (or drive):
- App will collect GPS points
- Check webhook logs for updates

4. Verify database:
```bash
sqlite3 location_tracking/locations.db \
  "SELECT * FROM locations ORDER BY timestamp DESC LIMIT 5;"
```

### TestFlight Beta

1. Archive app in Xcode
2. Upload to App Store Connect
3. Submit for review
4. Invite beta testers
5. Test with real users

---

## Production Deployment

### 1. App Store Connect Setup

1. Create app: https://appstoreconnect.apple.com
2. Bundle ID: `com.transmogrifier.app`
3. App Name: Transmogrifier
4. Category: Productivity
5. Age Rating: 4+ (no sensitive content)

### 2. Privacy Policy

**Required for location tracking:**
- Why you collect location
- How you use it
- Where it's stored
- User's rights

Host at: `https://transmogrifier.app/privacy`

### 3. App Review

**Location justification:**
- "We use location to detect when you arrive at/leave places like home, office, gym"
- "This enables automated workflow adjustments (e.g., block calendar during commute)"
- "Location data stays on user's private server, never shared"

**Background location justification:**
- "Background location is required to detect geofence entry/exit events"
- "We use 'significant location changes' not continuous GPS (battery-efficient)"

### 4. Submission Checklist

- [ ] App icon (1024x1024)
- [ ] Screenshots (all iPhone sizes)
- [ ] App description
- [ ] Keywords
- [ ] Privacy policy URL
- [ ] Support URL
- [ ] Age rating
- [ ] Export compliance (no encryption besides HTTPS)

### 5. Review Time

- Typical: 1-3 days
- If rejected: Address issues, resubmit
- Location apps: Sometimes extra scrutiny

---

## Troubleshooting

### Location Permission Denied

**Symptoms:** App doesn't track, no GPS updates

**Fix:**
1. Settings → Privacy → Location Services
2. Find "Transmogrifier"
3. Change to "Always Allow"

### Background Tracking Stops

**Symptoms:** No updates when app in background

**Fix:**
1. Check Info.plist has `UIBackgroundModes` → `location`
2. Verify `allowsBackgroundLocationUpdates = true`
3. Ensure "Always Allow" permission granted

### Webhook Sync Fails

**Symptoms:** No data in database despite GPS working

**Fix:**
1. Check API URL is correct
2. Verify auth token is valid
3. Check network connectivity
4. Review webhook logs for errors

### High Battery Drain

**Symptoms:** >10% battery drain per day

**Fix:**
1. Verify using `significantChangeOnly = true`
2. Don't use `startUpdatingLocation()` (continuous GPS)
3. Increase sync interval (5 min → 15 min)

---

## Code Structure

```
ios/
├── TransmogrifierApp.swift    # Main app + SwiftUI views
├── LocationTracker.swift      # Core location tracking logic
├── Info.plist                 # Permissions + background config
└── README.md                  # This file
```

**Key classes:**
- `LocationTracker`: Singleton managing CLLocationManager
- `AppDelegate`: App lifecycle + background setup
- `ContentView`: UI for configuration

---

## Next Steps

1. **Create Xcode project** (10 min)
2. **Add files to project** (5 min)
3. **Test on device** (30 min)
4. **Submit to TestFlight** (1 hour)
5. **Beta test** (1 week)
6. **Submit to App Store** (2 hours)
7. **Wait for review** (1-3 days)
8. **Launch!** 🚀

---

## Resources

- [Apple Location Documentation](https://developer.apple.com/documentation/corelocation)
- [Background Execution Guide](https://developer.apple.com/documentation/uikit/app_and_environment/scenes/preparing_your_ui_to_run_in_the_background)
- [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

---

## Status

✅ Code complete  
✅ Info.plist configured  
✅ Background modes enabled  
⏳ Xcode project needed  
⏳ TestFlight submission needed  
⏳ App Store submission needed  

**Estimated time to production:** 1-2 weeks (including App Store review)
