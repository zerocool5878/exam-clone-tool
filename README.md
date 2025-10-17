# Exam Clone Tool 🎯

An intelligent tool for comparing exam files and generating question ID mapping reports with automatic conflict resolution.

## ✨ Features

- 🔍 **Smart File Comparison**: Compare target exams with test exams to identify question mappings
- 🔄 **Conflict Resolution**: Automatically resolves duplicate ID assignments with intelligent alternatives
- 📊 **Detailed Reports**: Comprehensive mapping analysis with success statistics
- ⚡ **Auto-Updates**: Automatically checks for and installs updates from GitHub
- 🎯 **Multi-Format Support**: Works with normal target files and comprehensive test files
- 📈 **Progress Tracking**: Real-time analysis progress with detailed status updates

## 🚀 Quick Start

### Download & Install
1. Go to [Releases](https://github.com/zerocool5878/exam-clone-tool/releases)
2. Download the latest `.exe` file
3. Run directly - no installation required!

### Usage
1. **Launch**: Double-click the `.exe` file
2. **Auto-Update**: The tool checks for updates on startup
3. **Select Files**:
   - Click "📁 Select TARGET file" (your reference exam)
   - Click "📁 Select TEST file" (exam to compare)
4. **Generate Report**: Click "🔄 Generate Clone Report"
5. **Review Results**: Check mapping suggestions and statistics

## 🔧 Auto-Update System

The tool includes a built-in auto-update system:

- ✅ **Automatic Checking**: Checks GitHub releases on startup
- 📥 **One-Click Updates**: Download and install updates with progress tracking
- 🔄 **Seamless Restart**: Automatically restarts after successful update
- 🛡️ **Backup & Recovery**: Creates backups and handles rollback if needed

### Update Process
1. Tool starts → Checks GitHub for latest release
2. If update available → Shows update dialog
3. User clicks "Install Update" → Downloads new version
4. Replaces current exe → Restarts automatically

## 🏗️ Development

### Building from Source

#### Prerequisites
```bash
pip install pyinstaller requests
```

#### Build Executable
```bash
python build_release.py
```

#### Manual Build
```bash
pyinstaller --onefile --windowed --name "Exam_Clone_Tool_v1.0.0" --add-data "auto_updater.py;." exam_clone_tool_v2.py
```

### Creating Releases

#### Automated (GitHub Actions)
1. Update version in `exam_clone_tool_v2.py`:
   ```python
   VERSION = "1.1.0"  # Update this
   ```
2. Commit and push changes
3. Create and push a version tag:
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```
4. GitHub Actions automatically builds and creates the release

#### Manual Release
1. Run build script: `python build_release.py`
2. Go to GitHub → Releases → Create new release
3. Upload the `.exe` file from `releases/` folder
4. Publish release

## 📁 Project Structure

```
exam-clone-tool/
├── exam_clone_tool_v2.py      # Main application
├── auto_updater.py            # Auto-update system
├── build_release.py           # Build script
├── requirements.txt           # Dependencies
├── .github/workflows/         # GitHub Actions
│   └── release.yml           # Automated release workflow
└── releases/                 # Built executables (local)
```

## 🔄 Conflict Resolution Algorithm

The tool uses a sophisticated multi-phase conflict resolution system:

1. **Detection**: Identifies when multiple questions map to the same target ID
2. **Alternative Search**: Finds valid alternatives for conflicting mappings
3. **Validation**: Ensures alternatives meet all constraints:
   - Must be a main question (not sub-question)
   - Cannot already be assigned in the exam
   - Cannot be a previously suggested replacement
4. **Iterative Resolution**: Continues until all conflicts are resolved

## 📊 Report Features

- **Success Rate**: Percentage of successfully mapped questions
- **Change Tracking**: Questions needing ID updates
- **Conflict Detection**: Duplicate assignments with resolutions
- **Unknown IDs**: Questions not found in target file
- **Summary Statistics**: Complete mapping overview

## �️ System Requirements

- **OS**: Windows 10 or later
- **Internet**: Required for auto-updates
- **Memory**: Minimal (typically < 50MB)
- **Storage**: < 10MB for executable

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 Version History

- **v1.0.0**: Initial release with auto-update system
- **v0.9.x**: Conflict resolution implementation
- **v0.8.x**: Core mapping algorithm

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/zerocool5878/exam-clone-tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zerocool5878/exam-clone-tool/discussions)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

Built with ❤️ using Python | Auto-updates powered by GitHub 🚀