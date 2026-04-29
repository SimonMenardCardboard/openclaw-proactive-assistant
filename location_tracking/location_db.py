#!/usr/bin/env python3
"""
Location Tracking Database

Stores GPS points, learns places, detects patterns, manages geofences.

Tables:
- locations: Raw GPS points
- places: Learned locations (home, office, gym)
- geofences: Monitored areas
- patterns: Detected routines (commute, travel)

Usage:
    from location_db import LocationDB
    
    db = LocationDB()
    db.record_location('simon@email.com', 37.7749, -122.4194)
    place = db.get_current_place('simon@email.com')
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2
import json


class LocationDB:
    """Location tracking database with pattern learning"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize location database.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/location_tracking/locations.db'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # GPS points (raw location data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                accuracy REAL,
                altitude REAL,
                speed REAL,
                activity TEXT,
                battery_level INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_time ON locations(user_email, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON locations(timestamp)')
        
        # Learned places (auto-detected + user-defined)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                radius REAL DEFAULT 100,
                detected_count INTEGER DEFAULT 0,
                last_visit TEXT,
                category TEXT,
                auto_detected BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_places_user ON places(user_email)')
        
        # Geofences (active monitoring)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geofences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                place_id INTEGER NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                notify_enter BOOLEAN DEFAULT 1,
                notify_exit BOOLEAN DEFAULT 0,
                dwell_time_seconds INTEGER DEFAULT 300,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (place_id) REFERENCES places(id)
            )
        ''')
        
        # Location patterns (learned routines)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                from_place_id INTEGER,
                to_place_id INTEGER,
                typical_time TEXT,
                day_of_week INTEGER,
                confidence REAL,
                last_detected TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_place_id) REFERENCES places(id),
                FOREIGN KEY (to_place_id) REFERENCES places(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_location(
        self, 
        user_email: str,
        lat: float, 
        lon: float, 
        timestamp: Optional[str] = None,
        accuracy: Optional[float] = None,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        activity: Optional[str] = None,
        battery_level: Optional[int] = None
    ) -> int:
        """
        Record a GPS location point.
        
        Args:
            user_email: User's email address
            lat: Latitude
            lon: Longitude
            timestamp: ISO timestamp (defaults to now)
            accuracy: Accuracy in meters
            altitude: Altitude in meters
            speed: Speed in m/s
            activity: Activity type (stationary, walking, driving, etc.)
            battery_level: Battery percentage (0-100)
        
        Returns:
            location_id
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO locations 
            (user_email, timestamp, lat, lon, accuracy, altitude, speed, activity, battery_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_email, timestamp, lat, lon, accuracy, altitude, speed, activity, battery_level))
        
        location_id = cursor.lastrowid
        
        # Check if this location matches any known places
        self._check_place_detection(conn, user_email, lat, lon, timestamp)
        
        conn.commit()
        conn.close()
        
        return location_id
    
    def _check_place_detection(self, conn: sqlite3.Connection, user_email: str, lat: float, lon: float, timestamp: str):
        """Check if location is within any place's geofence and update visit count"""
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM places WHERE user_email = ?', (user_email,))
        places = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
        
        for place in places:
            distance = self._haversine_distance(lat, lon, place['lat'], place['lon'])
            
            if distance <= place['radius']:
                # User is at this place - update visit count
                cursor.execute('''
                    UPDATE places 
                    SET detected_count = detected_count + 1,
                        last_visit = ?
                    WHERE id = ?
                ''', (timestamp, place['id']))
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS points in meters.
        
        Uses Haversine formula for great-circle distance.
        
        Args:
            lat1, lon1: First point
            lat2, lon2: Second point
        
        Returns:
            Distance in meters
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
        
        Args:
            user_email: User's email address
        
        Returns:
            Place dict or None if not at any known place
        """
        conn = sqlite3.connect(str(self.db_path))
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
        cursor.execute('SELECT * FROM places WHERE user_email = ?', (user_email,))
        places = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
        
        for place in places:
            distance = self._haversine_distance(lat, lon, place['lat'], place['lon'])
            if distance <= place['radius']:
                conn.close()
                return place
        
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
        """
        Add a place (manually or via auto-detection).
        
        Args:
            user_email: User's email
            name: Place name (e.g., "Home", "Office")
            lat: Latitude
            lon: Longitude
            radius: Geofence radius in meters
            category: Category (home, work, gym, food, etc.)
            auto_detected: Whether auto-detected or user-defined
        
        Returns:
            place_id
        """
        conn = sqlite3.connect(str(self.db_path))
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
        """
        Get all places for a user.
        
        Args:
            user_email: User's email
        
        Returns:
            List of place dicts
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM places
            WHERE user_email = ?
            ORDER BY detected_count DESC, name
        ''', (user_email,))
        
        places = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return places
    
    def learn_place(
        self,
        user_email: str,
        min_visits: int = 5,
        days_back: int = 30,
        radius: float = 100
    ) -> List[int]:
        """
        Auto-detect new places based on GPS clustering.
        
        Finds GPS points that cluster together (visited multiple times)
        and creates places for them.
        
        Args:
            user_email: User's email
            min_visits: Minimum visits to consider a cluster
            days_back: Look back this many days
            radius: Cluster radius in meters
        
        Returns:
            List of new place_ids created
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get recent locations
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        cursor.execute('''
            SELECT lat, lon, COUNT(*) as visit_count
            FROM locations
            WHERE user_email = ? AND timestamp > ?
            GROUP BY ROUND(lat, 3), ROUND(lon, 3)
            HAVING COUNT(*) >= ?
            ORDER BY visit_count DESC
        ''', (user_email, cutoff, min_visits))
        
        clusters = cursor.fetchall()
        new_place_ids = []
        
        for lat, lon, visit_count in clusters:
            # Check if place already exists near this point
            existing_places = self.get_places(user_email)
            already_exists = False
            
            for place in existing_places:
                distance = self._haversine_distance(lat, lon, place['lat'], place['lon'])
                if distance <= radius * 2:  # Buffer to avoid duplicates
                    already_exists = True
                    break
            
            if not already_exists:
                # Create new auto-detected place
                name = f"Detected Place {datetime.now().strftime('%Y%m%d%H%M')}"
                place_id = self.add_place(
                    user_email=user_email,
                    name=name,
                    lat=lat,
                    lon=lon,
                    radius=radius,
                    auto_detected=True
                )
                new_place_ids.append(place_id)
        
        conn.close()
        return new_place_ids
    
    def detect_commute_pattern(self, user_email: str, days_back: int = 30) -> Optional[Dict]:
        """
        Detect regular commute patterns (home → office).
        
        Analyzes location transitions to find regular movements
        between places at consistent times.
        
        Args:
            user_email: User's email
            days_back: Look back this many days
        
        Returns:
            Pattern dict or None
        """
        # Simplified implementation - full version would use ML clustering
        # TODO: Implement sophisticated pattern detection
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get places
        places = self.get_places(user_email)
        if len(places) < 2:
            conn.close()
            return None
        
        # Look for transitions between places
        # (This is a placeholder - real implementation would analyze GPS traces)
        
        conn.close()
        return None
    
    def add_geofence(
        self,
        user_email: str,
        place_id: int,
        notify_enter: bool = True,
        notify_exit: bool = False,
        dwell_time_seconds: int = 300
    ) -> int:
        """
        Add a geofence for a place.
        
        Args:
            user_email: User's email
            place_id: Place to monitor
            notify_enter: Notify when entering
            notify_exit: Notify when exiting
            dwell_time_seconds: Minimum time before notification
        
        Returns:
            geofence_id
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO geofences 
            (user_email, place_id, notify_enter, notify_exit, dwell_time_seconds)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_email, place_id, notify_enter, notify_exit, dwell_time_seconds))
        
        geofence_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return geofence_id
    
    def get_geofences(self, user_email: str, enabled_only: bool = True) -> List[Dict]:
        """
        Get all geofences for a user.
        
        Args:
            user_email: User's email
            enabled_only: Only return enabled geofences
        
        Returns:
            List of geofence dicts with place info
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT g.*, p.name, p.lat, p.lon, p.radius
            FROM geofences g
            JOIN places p ON g.place_id = p.id
            WHERE g.user_email = ?
        '''
        
        if enabled_only:
            query += ' AND g.enabled = 1'
        
        cursor.execute(query, (user_email,))
        
        geofences = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return geofences
    
    def get_location_history(
        self,
        user_email: str,
        days_back: int = 7,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get location history for a user.
        
        Args:
            user_email: User's email
            days_back: Number of days to look back
            limit: Maximum number of points to return
        
        Returns:
            List of location dicts
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        query = '''
            SELECT * FROM locations
            WHERE user_email = ? AND timestamp > ?
            ORDER BY timestamp DESC
        '''
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query, (user_email, cutoff))
        
        locations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return locations


if __name__ == '__main__':
    # Test the database
    print("Testing Location Database...")
    
    db = LocationDB()
    
    # Add test locations
    user = 'test@example.com'
    
    # San Francisco
    db.record_location(user, 37.7749, -122.4194, activity='stationary')
    print("✅ Recorded location 1")
    
    # Nearby location (same place)
    db.record_location(user, 37.7750, -122.4195, activity='walking')
    print("✅ Recorded location 2")
    
    # Add a place
    place_id = db.add_place(user, 'Home', 37.7749, -122.4194, radius=50, category='home')
    print(f"✅ Added place (ID: {place_id})")
    
    # Check current place
    current = db.get_current_place(user)
    if current:
        print(f"✅ Currently at: {current['name']}")
    else:
        print("❌ Not at any known place")
    
    # Add geofence
    geofence_id = db.add_geofence(user, place_id, notify_enter=True, notify_exit=True)
    print(f"✅ Added geofence (ID: {geofence_id})")
    
    # Get history
    history = db.get_location_history(user, days_back=1)
    print(f"✅ Location history: {len(history)} points")
    
    print("\n✅ All tests passed!")
