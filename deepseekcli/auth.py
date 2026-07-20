from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Iterable


class AuthStorage:
    def __init__(self, login_dir: Path = Path(".login")):
        self.login_dir = login_dir
        self.credentials_path = self.login_dir / "credentials.json"
        self.backup_dir = self.login_dir / "backup"

    def ensure_dirs(self) -> None:
        self.login_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save_credentials(self, token: str, cookies: str) -> None:
        self.ensure_dirs()
        data = {"token": token.strip(), "cookies": cookies.strip()}
        self.credentials_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(self.credentials_path, 0o600)
        except OSError:
            pass

    def load_credentials(self) -> dict[str, str]:
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}. Use the CLI or save token/cookies first."
            )
        raw = self.credentials_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if "token" not in data or "cookies" not in data:
            raise ValueError(f"Invalid credentials file: {self.credentials_path}")
        return {"token": data["token"], "cookies": data["cookies"]}

    def backup_files(self, files: Iterable[Path]) -> None:
        self.ensure_dirs()
        for source in files:
            if not source.exists():
                continue
            destination = self.backup_dir / source.name
            shutil.copy2(source, destination)
