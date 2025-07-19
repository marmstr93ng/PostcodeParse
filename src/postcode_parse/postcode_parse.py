import argparse
import atexit
import glob
import os
import subprocess
import sys
from typing import Set, Tuple

import questionary
from _constants import SystemDefs
from _log import create_logger
from _version import __version__
from data_processing import data_transformation, postcode_parse
from io_utils import copy_directory_contents, create_folder, read_space_path, write_space_path
from updater import UpdateManager, VersionCheckError


def handle_updates() -> None:
    """Check for updates and handle installation process."""
    try:
        updater = UpdateManager(
            current_version=__version__, repo=SystemDefs.GITHUB_REPO, installer_name=SystemDefs.INSTALLER_NAME
        )

        update_available, version_message = updater.check_version()
        logger.info(version_message)

        if update_available and prompt_update(version_message):
            installer_path = updater.download_installer()
            logger.info(f"🚀 Launching installer: {installer_path}")
            subprocess.Popen([installer_path])
            sys.exit(0)

    except VersionCheckError as e:
        logger.error(str(e))


def prompt_event_action() -> str:
    return questionary.select(
        "🪜 What would you like to do?", choices=["Create New Event", "Modify Postcodes In Existing Event"]
    ).ask()


def prompt_update(version_info: str) -> bool:
    """User confirmation dialog with rich formatting"""
    return questionary.confirm(f"🎯 {version_info}\n🔧 Install update now?", default=True, auto_enter=False).ask()


def event_date_format(month: str, year: str) -> str:
    return f"{month}{year}"


def guided_option_entry() -> Tuple[str, str, str, Set[str], bool]:
    """Guide user through interactive parameter collection.

    Returns:
        Tuple containing:
        - space_path (str): Path to Google Drive directory
        - event_location (str): Location name for the event
        - event_date (str): Formatted as MonthYear (e.g. 'April2025')
        - postcode_districts (Set[str]): Set of cleaned postcode districts,
        - modify (bool): Flag if action is to modify an event
    """
    space_path = read_space_path()
    if not os.path.isdir(space_path):
        space_path = questionary.path("📁 What is the path to the SeedSower's Google Drive space?").ask()

    is_modify = prompt_event_action() == "Modify Postcodes In Existing Event"

    if is_modify:
        events_dir = os.path.join(space_path, SystemDefs.EVENTS_FOLDER_NAME)
        available_events = [d for d in os.listdir(events_dir) if os.path.isdir(os.path.join(events_dir, d))]
        selected_event = questionary.select("📂 Select event to modify:", choices=available_events).ask()
        event_location, event_date = selected_event.rsplit("_", 1)
    else:
        event_location = questionary.text("📍 What is the Seedsower's event location?").ask()
        month = questionary.select("📅 Select event month:", choices=SystemDefs.MONTHS).ask()
        year = questionary.select("📅 Select event year:", choices=SystemDefs.YEARS).ask()
        event_date = event_date_format(month, year)

    districts_input = questionary.text("✉️ Enter all postcode districts of the event (comma-separated: CV1,CV5):").ask()
    districts = {d.strip() for d in districts_input.split(",") if d.strip()}

    return space_path, event_location, event_date, districts, is_modify


def _create_guided_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configure guided mode CLI parser.

    Args:
        subparsers: Main parser's subparser collection

    Returns:
        Configured ArgumentParser for guided mode
    """
    parser = subparsers.add_parser(
        "guided",
        help="Interactive mode that guides you through parameter entry",
        description="\033[1mInteractive Mode\033[0m\nWalk through configuration step-by-step with helpful prompts",
    )
    return parser


def _create_manual_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configure manual mode CLI parser.

    Args:
        subparsers: Main parser's subparser collection

    Returns:
        Configured ArgumentParser for manual mode
    """
    manual_parser = subparsers.add_parser(
        "manual",
        help="Direct CLI argument entry",
        description="\033[1mManual Mode\033[0m\nProvide all parameters through command arguments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
            python script.py manual -s "C:/Google Drive/SeedSower" -e Belfast -m April -y 2025 -p BT1 BT2
            python script.py manual --space_path "~/SeedSower" --event_location Derry \\
                --event_month May --event_year 2025 --postcode_districts BT48 BT49""",
    )

    manual_parser.add_argument(
        "--modify",
        action="store_true",
        help="Modify an existing event instead of creating a new one (folder must already exist)",
    )

    manual_parser.add_argument(
        "-s",
        "--space_path",
        required=True,
        help="Path to SeedSower's Google Drive space (e.g. 'C:/Google Drive/SeedSower')",
    )

    manual_parser.add_argument(
        "-e", "--event_location", required=True, help="Event location name (e.g. 'Belfast' or 'Londonderry')"
    )

    manual_parser.add_argument(
        "-m", "--event_month", required=True, choices=SystemDefs.MONTHS, help="Event month (e.g. 'April')"
    )
    manual_parser.add_argument(
        "-y",
        "--event_year",
        required=True,
        choices=SystemDefs.YEARS,
        help=f"Event year (one of: {', '.join(SystemDefs.YEARS)})",
    )

    manual_parser.add_argument(
        "-p",
        "--postcode_districts",
        nargs="+",
        required=True,
        help="Postcode districts to extract (space-separated: BT1 BT2 BT3)",
    )

    return manual_parser


def parse_arguments() -> argparse.Namespace:
    """Configure and parse command line arguments.

    Returns:
        Namespace containing parsed arguments and selected mode
    """
    parser = argparse.ArgumentParser(
        description="\033[1mPostcode Processing Tool\033[0m\nAutomates event folder creation and data processing",
        epilog="For interactive guidance, use 'guided' mode without additional arguments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        title="Operation Modes", description="Select preferred operation method", dest="mode", metavar="MODE"
    )

    _create_guided_parser(subparsers)
    _create_manual_parser(subparsers)

    parser.set_defaults(mode="guided")
    return parser.parse_args()


def create_event_folder_structure(space_path: str, event_location: str, event_date: str) -> str:
    """Create directory structure for new event."""
    event_path = os.path.join(space_path, SystemDefs.EVENTS_FOLDER_NAME, f"{event_location}_{event_date}")
    logger.info(f"Event path: {event_path}")

    if os.path.isdir(event_path):
        logger.error(f"Failure: The event folder '{event_path}' already exists.")
        sys.exit(1)

    create_folder(event_path)
    create_folder(os.path.join(event_path, "Output"))
    return event_path


def remove_txt_files_from_event(event_path: str) -> None:
    """Deletes all .txt files in the specified event folder and its subfolders."""
    txt_files = glob.glob(os.path.join(event_path, "**", "*.txt"), recursive=True)
    for file_path in txt_files:
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Removed: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete {file_path}: {e}")


def setup_qgis_template(space_path: str, event_path: str, event_location: str) -> None:
    """Configure QGIS template files for the event."""
    qgis_template_folder_path = os.path.join(space_path, SystemDefs.QGIS_TEMPLATE_FOLDER_NAME)
    copy_directory_contents(qgis_template_folder_path, event_path)

    qgis_file_path = os.path.join(event_path, "Template.qgz")
    new_qgis_file_path = os.path.join(event_path, f"{event_location}.qgz")
    os.rename(qgis_file_path, new_qgis_file_path)


def process_data(space_path: str, postcode_districts: Set[str], event_path: str) -> None:
    """Process geographical data and launch event folder."""
    data_folder_path = os.path.join(space_path, SystemDefs.DATA_FOLDER_NAME)

    paf_file_path, ons_data_path = data_transformation(data_folder_path, postcode_districts)
    postcode_parse(paf_file_path, ons_data_path, postcode_districts, event_path)


if __name__ == "__main__":
    create_folder(SystemDefs.BASE_DIRECTORY)
    logger = create_logger(file_append=False)
    handle_updates()
    atexit.register(input, "Press Enter to exit...")

    args = parse_arguments()
    if args.mode == "guided":
        space_path, event_location, event_date, postcode_districts, is_modify = guided_option_entry()
    else:
        space_path = args.space_path
        event_location = args.event_location
        event_date = event_date_format(args.event_month, args.event_year)
        postcode_districts = set(args.postcode_districts)
        is_modify = args.modify

    write_space_path(space_path)

    if is_modify:
        event_path = os.path.join(space_path, SystemDefs.EVENTS_FOLDER_NAME, f"{event_location}_{event_date}")
        if not os.path.isdir(event_path):
            logger.error(f"❌ Event folder does not exist: {event_path}")
            sys.exit(1)
        logger.info(f"🔧 Modifying event: {event_path}")
        remove_txt_files_from_event(event_path)
    else:
        event_path = create_event_folder_structure(space_path, event_location, event_date)
        setup_qgis_template(space_path, event_path, event_location)

    process_data(space_path=space_path, postcode_districts=set(postcode_districts), event_path=event_path)

    os.startfile(event_path)
