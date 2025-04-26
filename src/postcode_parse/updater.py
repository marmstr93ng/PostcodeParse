import logging
import os
from typing import Tuple

import requests
from _constants import SystemDefs
from packaging.version import Version

logger = logging.getLogger(__name__)


class UpdateManager:
    """Centralized update management with GitHub integration"""

    def __init__(self, current_version: str, repo: str, installer_name: str) -> None:
        """Initialize UpdateManager with version information and repository details.

        Args:
            current_version: Currently installed version of the application
            repo: GitHub repository path in format 'owner/repo'
            installer_name: Filename of the installer to look for in releases
        """
        self.current_version = current_version
        self.repo = repo
        self.installer_name = installer_name
        self.base_dir = SystemDefs.BASE_DIRECTORY

    def check_version(self) -> Tuple[bool, str]:
        """Check GitHub for newer releases"""
        try:
            latest = self._get_latest_release()
            latest_version = latest["tag_name"].lstrip("v")

            if Version(latest_version) > Version(self.current_version):
                return True, f"🆕 Update {latest_version} available (Current: {self.current_version})"
            return False, f"✅ Current version {self.current_version} is latest"

        except requests.RequestException as e:
            raise VersionCheckError(f"Connection failed: {str(e)}") from e
        except Exception as e:
            raise VersionCheckError(f"Version check error: {str(e)}") from e

    def _get_latest_release(self) -> dict:
        """Internal method to fetch GitHub release data"""
        response = requests.get(f"https://api.github.com/repos/{self.repo}/releases/latest", timeout=10)
        response.raise_for_status()
        return response.json()

    def download_installer(self) -> str:
        """Download latest installer binary"""
        try:
            release = self._get_latest_release()
            asset = next((a for a in release.get("assets", []) if a["name"] == self.installer_name), None)

            if not asset:
                raise VersionCheckError(f"Installer '{self.installer_name}' not found")

            download_path = os.path.join(self.base_dir, self.installer_name)
            self._download_file(asset["browser_download_url"], download_path)
            return download_path

        except requests.RequestException as e:
            raise VersionCheckError(f"Download failed: {str(e)}") from e

    def _download_file(self, url: str, save_path: str) -> None:
        """Generic file download helper"""
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)


class VersionCheckError(Exception):
    """Custom exception for update-related errors"""

    def __init__(self, message: str) -> None:
        """Initialize VersionCheckError with a custom message

        Args:
            message: Human-readable error description
        """
        super().__init__(f"🛑 Update Error: {message}")
