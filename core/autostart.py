"""Cross-platform autostart management for HAROID on PC boot.

Supports Windows Registry (Run key), Windows Startup folder shortcut/VBS,
and macOS/Linux desktop entries.
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "HAROID"
VBS_SCRIPT_PATH = BASE_DIR / "scripts" / "start_haroid_silent.vbs"
BAT_SCRIPT_PATH = BASE_DIR / "scripts" / "start_haroid.bat"


def get_windows_startup_command() -> str:
    """Return the optimal command or path to run HAROID silently on Windows startup."""
    if VBS_SCRIPT_PATH.exists():
        return f'wscript.exe "{VBS_SCRIPT_PATH}"'
    python_exe = sys.executable
    # Prefer pythonw.exe if available to avoid opening a console window
    pythonw_exe = Path(python_exe).parent / "pythonw.exe"
    if pythonw_exe.exists():
        python_exe = str(pythonw_exe)
    main_py = BASE_DIR / "main.py"
    return f'"{python_exe}" "{main_py}" --background'


def is_windows() -> bool:
    return sys.platform == "win32"


def is_autostart_enabled() -> bool:
    """Check if HAROID is currently registered to start on PC boot."""
    if is_windows():
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            )
            try:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass

        # Check startup folder fallback
        startup_folder = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
        vbs_shortcut = startup_folder / "HAROID_Startup.vbs"
        bat_shortcut = startup_folder / "HAROID_Startup.bat"
        return vbs_shortcut.exists() or bat_shortcut.exists()
    return False


def enable_autostart(silent: bool = True) -> tuple[bool, str]:
    """Register HAROID to automatically start on Windows boot."""
    if not is_windows():
        return False, "Autostart registration currently supported on Windows."

    command = get_windows_startup_command()
    errors = []

    # 1. Register in Windows Registry (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        return True, f"HAROID successfully registered for Windows startup (Registry Run key: {command})."
    except Exception as exc:
        errors.append(f"Registry registration failed: {exc}")

    # 2. Fallback: Write silent launcher into Windows Startup folder
    try:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            startup_folder = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Startup"
            if startup_folder.exists():
                shortcut_file = startup_folder / "HAROID_Startup.vbs"
                vbs_content = (
                    f'Set WshShell = CreateObject("WScript.Shell")\r\n'
                    f'WshShell.Run "{command}", 0, False\r\n'
                )
                shortcut_file.write_text(vbs_content, encoding="utf-8")
                return True, f"HAROID startup launcher placed in: {shortcut_file}"
    except Exception as exc:
        errors.append(f"Startup folder registration failed: {exc}")

    return False, " | ".join(errors)


def disable_autostart() -> tuple[bool, str]:
    """Unregister HAROID from Windows startup."""
    if not is_windows():
        return False, "Autostart removal supported on Windows."

    removed_any = False
    errors = []

    # 1. Remove from Windows Registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, APP_NAME)
            removed_any = True
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)
    except Exception as exc:
        errors.append(f"Registry deletion error: {exc}")

    # 2. Remove from Startup folder if present
    try:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            startup_folder = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Startup"
            for filename in ["HAROID_Startup.vbs", "HAROID_Startup.bat"]:
                shortcut_file = startup_folder / filename
                if shortcut_file.exists():
                    shortcut_file.unlink()
                    removed_any = True
    except Exception as exc:
        errors.append(f"Startup folder removal error: {exc}")

    if removed_any:
        return True, "HAROID successfully removed from Windows startup."
    if errors:
        return False, " | ".join(errors)
    return True, "HAROID was not registered for Windows startup."


if __name__ == "__main__":
    if "--enable" in sys.argv:
        ok, msg = enable_autostart()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    elif "--disable" in sys.argv:
        ok, msg = disable_autostart()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    elif "--status" in sys.argv:
        enabled = is_autostart_enabled()
        print(f"HAROID autostart status: {'ENABLED' if enabled else 'DISABLED'}")
    else:
        print("Usage: python autostart.py [--enable | --disable | --status]")
