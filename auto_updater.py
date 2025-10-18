"""
Auto-Update System for Exam Clone Tool
Checks GitHub releases and downloads updates automatically
"""
import requests
import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
import time

class AutoUpdater:
    def __init__(self, current_version, repo_name, exe_name="Exam_Clone_Tool_v2.exe"):
        self.current_version = current_version
        self.repo_name = repo_name  # "zerocool5878/exam-clone-tool"
        self.exe_name = exe_name
        self.api_url = f"https://api.github.com/repos/{repo_name}/releases/latest"
        self.current_exe_path = self.get_current_exe_path()
        
    def get_current_exe_path(self):
        """Get the path of the currently running executable"""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            return sys.executable
        else:
            # Running as Python script (development)
            return __file__
    
    def check_for_updates(self):
        """Check if a newer version is available on GitHub"""
        try:
            print("🔍 Checking for updates...")
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data.get('tag_name', '').lstrip('v')
            download_url = None
            
            # Find the exe download URL
            for asset in release_data.get('assets', []):
                if asset['name'].endswith('.exe') or asset['name'] == self.exe_name:
                    download_url = asset['browser_download_url']
                    break
            
            if not download_url:
                print("❌ No executable found in latest release")
                return None, None, None
            
            # Compare versions
            if self.is_newer_version(latest_version, self.current_version):
                print(f"🆕 Update available: {self.current_version} → {latest_version}")
                return latest_version, download_url, release_data.get('body', '')
            else:
                print(f"✅ You have the latest version: {self.current_version}")
                return None, None, None
                
        except requests.RequestException as e:
            print(f"⚠️ Update check failed: {e}")
            return None, None, None
        except Exception as e:
            print(f"⚠️ Update check error: {e}")
            return None, None, None
    
    def is_newer_version(self, latest, current):
        """Compare version strings (semantic versioning)"""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            
            return latest_parts > current_parts
        except ValueError:
            # Fallback to string comparison
            return latest != current
    
    def download_update(self, download_url, progress_callback=None):
        """Download the update file"""
        try:
            print(f"⬇️ Downloading update from: {download_url}")
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="exam_tool_update_")
            temp_file = os.path.join(temp_dir, self.exe_name)
            
            # Download with progress
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress)
            
            print(f"✅ Download completed: {temp_file}")
            return temp_file
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return None
    
    def apply_update(self, new_exe_path):
        """Apply the update by creating a batch script to replace the exe after exit"""
        try:
            print("🔄 Applying update...")
            
            # Get directory paths
            current_dir = os.path.dirname(self.current_exe_path)
            current_exe_name = os.path.basename(self.current_exe_path)
            backup_path = os.path.join(current_dir, f"{current_exe_name}.backup")
            
            # Create update batch script
            batch_script = os.path.join(tempfile.gettempdir(), "exam_tool_update.bat")
            
            # Batch script will:
            # 1. Wait for current process to exit
            # 2. Backup current exe
            # 3. Copy new exe to current location
            # 4. Start new exe
            # 5. Delete itself
            batch_content = f'''@echo off
timeout /t 2 /nobreak >nul
echo Backing up current version...
copy /Y "{self.current_exe_path}" "{backup_path}" >nul
echo Installing update...
copy /Y "{new_exe_path}" "{self.current_exe_path}" >nul
echo Starting updated application...
start "" "{self.current_exe_path}"
echo Cleaning up...
del /F /Q "{new_exe_path}" >nul
rmdir "{os.path.dirname(new_exe_path)}" >nul 2>nul
del /F /Q "%~f0" >nul
'''
            
            with open(batch_script, 'w') as f:
                f.write(batch_content)
            
            print(f"✅ Update script created: {batch_script}")
            
            # Launch the update script and exit
            subprocess.Popen(['cmd', '/c', batch_script], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            
            print("🔄 Update will complete after application exits...")
            
            return True
            
        except Exception as e:
            print(f"❌ Update preparation failed: {e}")
            return False
    
    def restart_application(self):
        """Exit the application (update script will restart it)"""
        try:
            print("🔄 Exiting for update...")
            time.sleep(1)  # Give user time to see the message
            
            # Exit current process - batch script will restart
            sys.exit(0)
            
        except Exception as e:
            print(f"❌ Exit failed: {e}")
            return False
    
    def perform_update_check_and_install(self, auto_install=True, progress_callback=None):
        """Main update process"""
        try:
            # Check for updates
            latest_version, download_url, changelog = self.check_for_updates()
            
            if not latest_version:
                return False, "No updates available"
            
            if not auto_install:
                return True, f"Update available: {latest_version}"
            
            # Download update
            new_exe_path = self.download_update(download_url, progress_callback)
            if not new_exe_path:
                return False, "Download failed"
            
            # Apply update
            if self.apply_update(new_exe_path):
                # Restart application
                self.restart_application()
                return True, "Update completed successfully"
            else:
                return False, "Update installation failed"
                
        except Exception as e:
            return False, f"Update process failed: {e}"

def create_update_ui():
    """Create a simple update progress UI"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    
    class UpdateWindow:
        def __init__(self, updater):
            self.updater = updater
            self.root = tk.Tk()
            self.root.title("Exam Tool Updater")
            self.root.geometry("400x200")
            self.root.resizable(False, False)
            
            # Center the window
            self.root.transient()
            self.root.grab_set()
            
            self.setup_ui()
            
        def setup_ui(self):
            # Main frame
            main_frame = ttk.Frame(self.root, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="🔍 Checking for updates...", 
                                  font=("Arial", 12, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Progress bar
            self.progress = ttk.Progressbar(main_frame, mode='determinate', length=300)
            self.progress.pack(pady=(0, 10))
            
            # Status label
            self.status_label = ttk.Label(main_frame, text="Connecting to GitHub...")
            self.status_label.pack(pady=(0, 20))
            
            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack()
            
            self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel)
            self.cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            self.install_btn = ttk.Button(button_frame, text="Install Update", 
                                        command=self.install_update, state=tk.DISABLED)
            self.install_btn.pack(side=tk.LEFT)
            
        def update_progress(self, value, text=""):
            self.progress['value'] = value
            if text:
                self.status_label.config(text=text)
            self.root.update()
            
        def progress_callback(self, progress):
            self.update_progress(progress, f"Downloading... {progress:.1f}%")
            
        def check_for_updates(self):
            self.update_progress(20, "Checking GitHub releases...")
            
            latest_version, download_url, changelog = self.updater.check_for_updates()
            
            if latest_version:
                self.update_progress(100, f"Update available: {latest_version}")
                self.install_btn.config(state=tk.NORMAL)
                
                # Show changelog if available
                if changelog:
                    messagebox.showinfo("Update Available", 
                                      f"Version {latest_version} is available!\n\n{changelog[:200]}...")
                return True
            else:
                self.update_progress(100, "You have the latest version!")
                self.root.after(2000, self.root.destroy)
                return False
                
        def install_update(self):
            self.install_btn.config(state=tk.DISABLED)
            self.cancel_btn.config(state=tk.DISABLED)
            
            try:
                success, message = self.updater.perform_update_check_and_install(
                    auto_install=True, 
                    progress_callback=self.progress_callback
                )
                
                if success:
                    self.update_progress(100, "Update completed! Restarting...")
                    self.root.after(1000, self.root.destroy)
                else:
                    messagebox.showerror("Update Failed", message)
                    self.cancel_btn.config(state=tk.NORMAL)
                    
            except Exception as e:
                messagebox.showerror("Update Error", f"Update failed: {e}")
                self.cancel_btn.config(state=tk.NORMAL)
                
        def cancel(self):
            self.root.destroy()
            
        def run(self):
            # Start update check in background
            self.root.after(500, self.check_for_updates)
            self.root.mainloop()
    
    return UpdateWindow

if __name__ == "__main__":
    # Test the updater
    updater = AutoUpdater("1.0.0", "zerocool5878/exam-clone-tool")
    
    # Create update UI
    UpdateWindow = create_update_ui()
    window = UpdateWindow(updater)
    window.run()