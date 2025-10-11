# 📄 Exam Clone Tool

A Windows desktop application for comparing exam HTML files and generating mapping reports to clone exam questions with correct answers.

## 🚀 Features

- **Smart Mapping**: Automatically maps exam alternative answers to target main question IDs
- **HTML Processing**: Handles minified HTML exam files with proper question boundary detection
- **Clean Interface**: User-friendly GUI with step-by-step file selection
- **Detailed Reports**: Generates comprehensive mapping reports showing required changes
- **Standalone Executable**: No Python installation required - just run the .exe

## 📋 How to Use

1. **Select Target File**: Choose the file containing correct answers (answer key)
2. **Select Test File**: Choose the exam file you want to compare against the target
3. **Generate Report**: Click "Generate Clone Report" to see the mapping results

## 🔧 Algorithm

The tool uses advanced regex pattern matching to:
- Extract numbered questions from both files
- Identify main question IDs vs alternative answer IDs
- Map each exam alternative to its corresponding target main question
- Generate change instructions in format: `Question #X: Change (ID:current) → (ID:target)`

## 📊 Example Output

```
Question #1: ✅ Already correct (ID:107696)
Question #2: Change (ID:107647) → (ID:107649)
Question #3: Change (ID:107693) → (ID:107696)
```

## 💾 Files Included

- `fixed_mapping_tool.py` - Main Python source code
- `test_icon.ico` - Custom test sheet icon
- `ExamCloneTool.exe` - Standalone Windows executable
- `create_icon.py` - Icon generation script

## ⚙️ Technical Details

- **Language**: Python 3.13+ with tkinter GUI
- **Dependencies**: Built-in modules only (re, html, os, tkinter)
- **Platform**: Windows 10/11
- **Architecture**: 64-bit
- **Size**: ~10MB executable

## 🔨 Building from Source

To rebuild the executable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ExamCloneTool" --icon="test_icon.ico" fixed_mapping_tool.py
```

## 📝 License

This project is open source. Feel free to use, modify, and distribute.

## 🎯 Use Cases

- Educational institutions managing exam variations
- Test preparation companies creating practice exams  
- Quality assurance for exam content management
- Automated exam cloning and answer key verification

---

**Created with ❤️ for efficient exam management**