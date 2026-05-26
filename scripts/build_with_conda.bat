@echo off
call C:\ProgramData\anaconda3\Scripts\activate.bat py312
pip install -e .
pip install PySide6==6.6.3 pyinstaller
rmdir /S /Q build
rmdir /S /Q release
python scripts\build.py
