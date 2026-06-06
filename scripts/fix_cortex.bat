@echo off
echo Fixing cortex.py bare except:pass patterns and HIGH-65...
python "%~dp0fix_cortex_direct.py"
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Done! All patterns fixed in backend\ai\cortex.py
) else (
    echo.
    echo ERROR: Script failed with exit code %ERRORLEVEL%
)
echo.
pause
