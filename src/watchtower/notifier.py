from __future__ import annotations

import platform
import shutil
import subprocess

from watchtower.models import Intervention


class DesktopNotifier:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def notify(self, intervention: Intervention) -> bool:
        if not self.enabled:
            return False
        title = f"Watchtower: {intervention.title}"
        body = intervention.message[:500]
        system = platform.system()
        try:
            if system == "Darwin" and shutil.which("osascript"):
                script = (
                    f"display notification {self._apple_quote(body)} "
                    f"with title {self._apple_quote(title)}"
                )
                subprocess.run(
                    ["osascript", "-e", script],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
                return True
            if system == "Linux" and shutil.which("notify-send"):
                subprocess.run(
                    ["notify-send", title, body],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
                return True
            if system == "Windows" and shutil.which("powershell"):
                escaped_title = title.replace("'", "''")
                escaped_body = body.replace("'", "''")
                command = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$n=New-Object System.Windows.Forms.NotifyIcon; "
                    "$n.Icon=[System.Drawing.SystemIcons]::Information; "
                    "$n.Visible=$true; "
                    f"$n.ShowBalloonTip(5000,'{escaped_title}','{escaped_body}',0); "
                    "Start-Sleep -Seconds 1; $n.Dispose()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                return True
        except (OSError, subprocess.SubprocessError):
            return False
        return False

    @staticmethod
    def _apple_quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
