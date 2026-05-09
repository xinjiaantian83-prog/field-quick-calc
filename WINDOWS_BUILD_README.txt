SpriteAnchor Windows Build Guide
================================

Goal
----
Build a double-clickable Windows executable:

  dist\SpriteAnchor.exe
  dist\SpriteAnchor_windows.zip

Important
---------
PyInstaller does not normally cross-compile. Build the Windows .exe on a Windows PC.
The macOS .app build files are separate and should not be changed for Windows builds.

Files needed on the Windows PC
------------------------------
Copy the project folder containing at least these files:

  SpriteAnchor.py
  build_windows_exe.bat
  requirements_windows.txt
  SpriteAnchor_windows.spec

Recommended Windows setup
-------------------------
1. Install Python 3.11 or Python 3.12 from:
   https://www.python.org/downloads/windows/

2. During Python install, enable:
   Add python.exe to PATH

3. Copy this project folder to the Windows PC.

Build steps
-----------
1. Double-click:

   build_windows_exe.bat

2. Wait for it to:
   - create .venv-windows
   - install PyInstaller, Pillow, and tkinterdnd2
   - build dist\SpriteAnchor.exe
   - create dist\SpriteAnchor_windows.zip

3. Double-click:

   dist\SpriteAnchor.exe

4. If the app opens, upload this file to itch.io:

   dist\SpriteAnchor_windows.zip

Runtime dependency notes
------------------------
Tkinter is included with the official Python installer.
Pillow is bundled into the exe by PyInstaller.
tkinterdnd2 is included so drag and drop can work when supported.

rembg is intentionally not included in the Windows build requirements.
SpriteAnchor already treats rembg as optional and falls back to a simpler background-removal method if rembg is missing or broken. This keeps the exe smaller and prevents heavy ML dependencies from breaking app launch.

Windows verification checklist
------------------------------
Before uploading to itch.io:

  [ ] build_windows_exe.bat finishes without errors
  [ ] dist\SpriteAnchor.exe exists
  [ ] dist\SpriteAnchor_windows.zip exists
  [ ] Double-clicking SpriteAnchor.exe opens the app
  [ ] Add Sprites opens the file picker
  [ ] Loading a PNG/JPG shows a thumbnail and preview
  [ ] ALIGN / Fit controls still respond
  [ ] START export flow still opens and can save PNG output
  [ ] Remove BG does not crash the app even without rembg
  [ ] Closing and reopening the exe works

If SmartScreen appears
----------------------
Unsigned executables downloaded from itch.io may show a Windows SmartScreen warning.
For a smoother buyer experience, consider code-signing the .exe later with a Windows code-signing certificate.

Troubleshooting
---------------
If Python is not found:
  Reinstall Python 3.11 or 3.12 and enable "Add python.exe to PATH".

If pip install fails:
  Check internet access, then run build_windows_exe.bat again.

If the exe build fails:
  Read the first ERROR line in the build window.
  The detailed PyInstaller warnings are usually in:

    build\SpriteAnchor\warn-SpriteAnchor.txt

If SpriteAnchor.exe does not open:
  Open Command Prompt in the project folder and run:

    dist\SpriteAnchor.exe

  Then check whether Windows creates a crash report or prints an error.
