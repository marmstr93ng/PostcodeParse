import logging
import os
import shutil
import sys
from typing import Any, Dict

import yaml
from _constants import SystemDefs

logger = logging.getLogger(__name__)


def copy_directory_contents(source_dir: str, destination_dir: str) -> None:
    """Recursively copies contents from source directory to destination directory.

    Args:
        source_dir: Path to source directory
        destination_dir: Path to destination directory

    Raises:
        SystemExit: If source directory doesn't exist
    """
    if not os.path.exists(source_dir):
        logger.error(f"Source directory '{source_dir}' does not exist.")
        sys.exit(1)
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        destination_item = os.path.join(destination_dir, item)

        try:
            if os.path.isdir(source_item):
                shutil.copytree(source_item, destination_item)
            else:
                shutil.copy2(source_item, destination_item)
        except PermissionError:
            logger.warning(f"Skipping file due to permission error: {source_item}")


def create_folder(path: str) -> None:
    """Creates directory structure recursively if it doesn't exist.

    Args:
        path: Directory path to create
    """
    if not os.path.exists(path):
        os.makedirs(path)


def get_file_length(file_path: str) -> int:
    """Counts number of lines in a file.

    Args:
        file_path: Path to target file

    Returns:
        Number of lines in the file

    Note:
        Uses universal newline mode for cross-platform compatibility
    """
    logger.info(f"Getting file length for {file_path}")
    with open(file_path, newline="") as file:
        return sum(1 for _ in file)


def read_space_path() -> str:
    """Reads space_path setting from configuration file.

    Returns:
        Configured space_path if exists, empty string otherwise
    """
    try:
        with open(SystemDefs.SETTINGS_FILE) as file:
            settings: Dict[str, Any] = yaml.safe_load(file)
            return settings.get("space_path", "")
    except FileNotFoundError:
        return ""


def write_space_path(path: str) -> None:
    """Writes space_path setting to configuration file.

    Args:
        path: Path to store as space_path
    """
    settings: Dict[str, Any] = {"space_path": path}
    with open(SystemDefs.SETTINGS_FILE, "w") as file:
        yaml.dump(settings, file)
