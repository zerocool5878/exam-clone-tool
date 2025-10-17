"""
Build script for creating executable releases of the Exam Clone Tool
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def get_version():
    """Extract version from main application file"""
    with open('exam_clone_tool_v2.py', 'r', encoding='utf-8') as f:
        content = f.read()
        for line in content.split('\n'):
            if line.strip().startswith('VERSION = '):
                version = line.split('=')[1].strip().strip('"\'')
                return version
    return "1.0.0"

def build_executable():
    """Build the executable using PyInstaller"""
    version = get_version()
    exe_name = f"Exam_Clone_Tool_v{version}"
    
    print(f"🔨 Building executable: {exe_name}.exe")
    
    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',                    # Single file
        '--windowed',                   # No console window
        '--name', exe_name,             # Executable name
        '--icon=icon.ico',              # Icon (if exists)
        '--add-data', 'auto_updater.py;.',  # Include auto_updater
        'exam_clone_tool_v2.py'         # Main script
    ]
    
    # Add icon if it exists
    if not os.path.exists('icon.ico'):
        cmd.remove('--icon=icon.ico')
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Build successful!")
        
        # Move exe to releases folder
        releases_dir = Path('releases')
        releases_dir.mkdir(exist_ok=True)
        
        exe_path = Path('dist') / f"{exe_name}.exe"
        release_path = releases_dir / f"{exe_name}.exe"
        
        if exe_path.exists():
            shutil.move(str(exe_path), str(release_path))
            print(f"📦 Release created: {release_path}")
            
            # Clean up build artifacts
            if Path('build').exists():
                shutil.rmtree('build')
            if Path('dist').exists():
                shutil.rmtree('dist')
            
            spec_file = Path(f"{exe_name}.spec")
            if spec_file.exists():
                spec_file.unlink()
            
            return str(release_path)
        else:
            print(f"❌ Executable not found: {exe_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return None

def create_release_notes():
    """Create release notes file"""
    version = get_version()
    
    release_notes = f"""# Exam Clone Tool v{version}

## Features
- 🔍 Compare exam files and identify question ID mappings
- 🔄 Automatic conflict resolution for duplicate assignments
- 📊 Detailed mapping reports with success statistics
- ⚡ Auto-update system with GitHub integration
- 🎯 Support for both normal target and comprehensive test files

## What's New in v{version}
- ✨ Added auto-update system
- 🛠️ Improved conflict detection and resolution
- 📈 Enhanced progress reporting
- 🔧 Better error handling

## Installation
1. Download the .exe file
2. Run directly - no installation required
3. The tool will automatically check for updates on startup

## Usage
1. Select your TARGET file (reference exam)
2. Select your TEST file (exam to compare)
3. Click "Generate Clone Report"
4. Review the mapping suggestions

## System Requirements
- Windows 10 or later
- Internet connection (for updates)

---
Built with Python 🐍 | Auto-updates via GitHub 🚀
"""
    
    with open(f'releases/RELEASE_NOTES_v{version}.md', 'w', encoding='utf-8') as f:
        f.write(release_notes)
    
    print(f"📝 Release notes created: RELEASE_NOTES_v{version}.md")

def main():
    """Main build process"""
    print("🏗️ Starting build process...")
    
    # Check if PyInstaller is available
    try:
        subprocess.run(['pyinstaller', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller not found. Install with: pip install pyinstaller")
        return
    
    # Build executable
    exe_path = build_executable()
    
    if exe_path:
        # Create release notes
        create_release_notes()
        
        print("🎉 Build complete!")
        print(f"📁 Release files in: releases/")
        print("\n📋 Next steps:")
        print("1. Test the executable")
        print("2. Create GitHub release")
        print("3. Upload the .exe file as a release asset")
        print("4. Update version number for next release")
    else:
        print("❌ Build failed!")

if __name__ == "__main__":
    main()