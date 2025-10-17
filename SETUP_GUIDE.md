# 🚀 Exam Clone Tool - Installation & Update Guide

## 📥 First Time Setup

### Step 1: Install Dependencies
```bash
pip install requests pyinstaller
```

### Step 2: Test the Application
```bash
python exam_clone_tool_v2.py
```

## 🏗️ Creating Your First Release

### Step 1: Build the Executable
```bash
python build_release.py
```
This creates `releases/Exam_Clone_Tool_v1.0.0.exe`

### Step 2: Create GitHub Release
1. Go to your GitHub repository
2. Click **"Releases"** → **"Create a new release"**
3. Tag version: `v1.0.0`
4. Release title: `Exam Clone Tool v1.0.0`
5. Upload the `.exe` file from `releases/` folder
6. Click **"Publish release"**

### Step 3: Test Auto-Update
After creating the release:
```bash
# Test with older version to trigger update
python -c "
from auto_updater import AutoUpdater
updater = AutoUpdater('0.9.0', 'zerocool5878/exam-clone-tool')
result = updater.check_for_updates()
print('Update available:', result[0] is not None)
"
```

## 🔄 Future Updates

### Automated with GitHub Actions (Recommended)
1. **Update Version**: Edit `exam_clone_tool_v2.py`
   ```python
   VERSION = "1.1.0"  # Change this
   ```

2. **Commit & Tag**:
   ```bash
   git add .
   git commit -m "Release v1.1.0: Add new features"
   git tag v1.1.0
   git push origin main
   git push origin v1.1.0
   ```

3. **Automatic Build**: GitHub Actions will automatically:
   - Build the executable
   - Create the release
   - Upload the `.exe` file

### Manual Updates
1. Run `python build_release.py`
2. Go to GitHub → Releases → Create new release
3. Upload the new `.exe` file

## ✅ Verification Checklist

After each release:
- [ ] Executable runs without errors
- [ ] Auto-update system detects new version
- [ ] Update process completes successfully
- [ ] All core functionality works
- [ ] File selection and report generation work

## 🛠️ Troubleshooting

### "requests module not found"
```bash
pip install requests
```

### "pyinstaller not found"
```bash
pip install pyinstaller
```

### Auto-update fails
- Check internet connection
- Verify GitHub repository is public
- Ensure release has `.exe` file attached

### Build errors
- Ensure all Python files are in the same directory
- Check that `auto_updater.py` exists
- Verify Python version compatibility

## 📋 Update Process Flow

```
User starts .exe
       ↓
Check GitHub for latest release
       ↓
Compare versions (semantic versioning)
       ↓
If newer version found:
   ↓
Show update dialog
   ↓
Download new .exe
   ↓
Replace current .exe
   ↓
Restart application
```

## 🎯 Best Practices

1. **Version Numbering**: Use semantic versioning (1.0.0, 1.1.0, 2.0.0)
2. **Release Notes**: Include what's new in each release
3. **Testing**: Always test the executable before releasing
4. **Backup Strategy**: Keep previous versions available
5. **User Communication**: Announce major updates to users

---

**Ready to deploy? Your exam tool now has professional auto-update capabilities! 🚀**