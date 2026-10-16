@echo off
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%~dp0To-Do.lnk'); $s.TargetPath='%LOCALAPPDATA%\Python\bin\pythonw.exe'; $s.Arguments='%~dp0todo.pyw'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0todo.ico'; $s.Save()"
echo Shortcut created. You can close this window.
pause
