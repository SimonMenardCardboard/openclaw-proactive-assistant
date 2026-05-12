#!/usr/bin/env python3
"""
V8 Cross-Device Observer - Screen Capture Module

Captures screenshots from remote desktops using various protocols.

Supported protocols:
- macOS Screen Sharing (VNC on port 5900)
- VNC (cross-platform)
- Note: RDP support deferred (requires additional libraries)

Privacy features:
- Capture rate limiting
- Activity-based capture only (no continuous recording)
- Immediate processing and deletion of raw screenshots
- Encrypted storage of extracted data only
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import subprocess
import tempfile

logger = logging.getLogger('v8.cross_device.screen_capture')


class ScreenCapture:
    """Screen capture from remote desktop devices."""
    
    def __init__(self, privacy_mode: str = 'activity_only'):
        """
        Initialize screen capture.
        
        Args:
            privacy_mode: 'activity_only' (default) or 'full_capture'
        """
        self.privacy_mode = privacy_mode
        self.temp_dir = Path(tempfile.gettempdir()) / 'v8_screen_capture'
        self.temp_dir.mkdir(exist_ok=True)
        
        # Privacy settings
        self.max_capture_rate = 1  # Max 1 capture per second
        self.last_capture_time = None
        self.retain_raw_images = False  # Never keep raw screenshots
    
    def capture_vnc(self, host: str, port: int = 5900, 
                   password: Optional[str] = None) -> Optional[Path]:
        """
        Capture screenshot via VNC.
        
        Args:
            host: VNC server hostname or IP
            port: VNC port (default 5900)
            password: VNC password (optional)
            
        Returns:
            Path to captured screenshot or None
        """
        try:
            import vncdotool.api as vncapi
            from PIL import Image
            
            # Rate limiting
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded, skipping capture")
                return None
            
            # Connect to VNC server
            logger.info(f"Connecting to VNC server at {host}:{port}")
            
            # Use vncdotool to capture screen
            client = vncapi.connect(f"{host}::{port}", password=password)
            
            # Capture screenshot
            screenshot_path = self.temp_dir / f"vnc_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            client.captureScreen(str(screenshot_path))
            client.disconnect()
            
            logger.info(f"Screenshot captured: {screenshot_path}")
            
            return screenshot_path
            
        except ImportError:
            logger.error("vncdotool not installed. Install with: pip install vncdotool")
            return None
        except Exception as e:
            logger.error(f"Error capturing VNC screen: {e}")
            return None
    
    def capture_macos_screen_sharing(self, host: str = 'localhost', 
                                     port: int = 5900) -> Optional[Path]:
        """
        Capture screenshot from macOS Screen Sharing.
        
        This uses VNC protocol under the hood.
        
        Args:
            host: Screen Sharing host (default localhost for testing)
            port: Port (default 5900)
            
        Returns:
            Path to captured screenshot or None
        """
        logger.info(f"Capturing from macOS Screen Sharing at {host}:{port}")
        
        # macOS Screen Sharing is VNC-based
        return self.capture_vnc(host, port)
    
    def capture_localhost_screenshot(self) -> Optional[Path]:
        """
        Capture screenshot of localhost (for testing on Mac).
        
        Uses native screencapture command on macOS.
        
        Returns:
            Path to captured screenshot or None
        """
        try:
            # Rate limiting
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded, skipping capture")
                return None
            
            screenshot_path = self.temp_dir / f"localhost_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            # Use macOS native screencapture
            result = subprocess.run(
                ['screencapture', '-x', str(screenshot_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and screenshot_path.exists():
                logger.info(f"Localhost screenshot captured: {screenshot_path}")
                return screenshot_path
            else:
                logger.error(f"screencapture failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error capturing localhost screenshot: {e}")
            return None
    
    def cleanup_screenshot(self, screenshot_path: Path):
        """
        Delete screenshot after processing (privacy).
        
        Args:
            screenshot_path: Path to screenshot to delete
        """
        try:
            if screenshot_path and screenshot_path.exists():
                screenshot_path.unlink()
                logger.debug(f"Deleted screenshot: {screenshot_path}")
        except Exception as e:
            logger.error(f"Error deleting screenshot: {e}")
    
    def cleanup_all(self):
        """Delete all temporary screenshots."""
        try:
            for file in self.temp_dir.glob("*.png"):
                file.unlink()
            logger.info("Cleaned up all temporary screenshots")
        except Exception as e:
            logger.error(f"Error cleaning up screenshots: {e}")
    
    def _check_rate_limit(self) -> bool:
        """
        Check if capture is within rate limit.
        
        Returns:
            True if capture is allowed, False otherwise
        """
        now = datetime.now()
        
        if self.last_capture_time is None:
            self.last_capture_time = now
            return True
        
        elapsed = (now - self.last_capture_time).total_seconds()
        
        if elapsed < (1.0 / self.max_capture_rate):
            return False
        
        self.last_capture_time = now
        return True


if __name__ == '__main__':
    # Test screen capture
    print("\n=== Screen Capture Test ===\n")
    
    capture = ScreenCapture()
    
    # Test localhost capture (macOS)
    print("Testing localhost screenshot capture...")
    screenshot = capture.capture_localhost_screenshot()
    
    if screenshot:
        print(f"✓ Screenshot captured: {screenshot}")
        print(f"  Size: {screenshot.stat().st_size} bytes")
        
        # Clean up
        capture.cleanup_screenshot(screenshot)
        print("✓ Screenshot deleted (privacy mode)")
    else:
        print("✗ Screenshot capture failed")
    
    print("\nNote: VNC capture requires:")
    print("  1. Screen Sharing enabled on target Mac")
    print("  2. vncdotool installed: pip install vncdotool")
    print("  3. VNC password/authentication configured")
