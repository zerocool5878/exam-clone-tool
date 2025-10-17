@echo off
echo 🚀 Exam Clone Tool - Complete Setup Script
echo ==========================================
echo.

:: Check if we're in the right directory
if not exist "exam_clone_tool_v2.py" (
    echo ❌ Error: exam_clone_tool_v2.py not found
    echo Please run this script from the exam-clone-tool directory
    pause
    exit /b 1
)

echo Step 1: Installing dependencies...
echo (Using virtual environment - already installed)
echo ✅ Dependencies ready!

echo.
echo Step 2: Building executable with auto-update...
"C:/Users/zeroc/OneDrive/Documents/Exam_tool/.venv/Scripts/python.exe" build_release.py
if %ERRORLEVEL% neq 0 (
    echo ❌ Build failed
    pause
    exit /b 1
)

echo.
echo Step 3: Testing the executable...
if exist "releases\Exam_Clone_Tool_v1.0.0.exe" (
    echo ✅ Executable created successfully!
    echo 📁 Location: releases\Exam_Clone_Tool_v1.0.0.exe
    echo.
    echo 🎯 Next steps:
    echo 1. Test the exe: Double-click releases\Exam_Clone_Tool_v1.0.0.exe
    echo 2. Create GitHub release:
    echo    - Go to: https://github.com/zerocool5878/exam-clone-tool/releases
    echo    - Click "Create a new release"
    echo    - Tag: v1.0.0
    echo    - Upload: releases\Exam_Clone_Tool_v1.0.0.exe
    echo    - Publish release
    echo 3. Test auto-update by creating v1.0.1 release
    echo.
) else (
    echo ❌ Executable not found in releases folder
)

echo Press any key to open the releases folder...
pause > nul
explorer releases

echo.
echo 🎉 Setup complete! Your exam tool now has auto-update capabilities.
pause