#!/usr/bin/env python3
"""
Install platform-specific dependencies for desktop observer
"""

import sys
import subprocess

def install_dependencies():
    platform = sys.platform
    
    print(f"Detected platform: {platform}")
    
    if platform == 'darwin':
        # macOS - minimal dependencies (most are built-in)
        packages = []  # Pillow only needed for advanced screen capture
        print("macOS: No additional dependencies required")
        print("(Optional: pip install Pillow for enhanced screen capture)")
    
    elif platform == 'win32':
        # Windows
        packages = ['pywin32', 'psutil']
        print("Windows: Installing pywin32 and psutil...")
    
    elif platform in ['linux', 'linux2']:
        # Linux
        packages = ['python-xlib', 'psutil']
        print("Linux: Installing python-xlib and psutil...")
        print("Note: For Wayland, also install wmctrl via system package manager")
    
    else:
        print(f"❌ Unsupported platform: {platform}")
        return
    
    if packages:
        for package in packages:
            print(f"Installing {package}...")
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"  ✅ {package} installed")
            else:
                print(f"  ❌ Failed to install {package}")
                print(f"     {result.stderr}")
    
    print("\n✓ Dependencies check complete!")

if __name__ == '__main__':
    install_dependencies()
