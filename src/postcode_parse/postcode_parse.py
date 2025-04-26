import argparse
import atexit
import calendar
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Set, Tuple

import questionary
from _constants import SystemDefs
from _log import create_logger
from _version import __version__
from data_processing import data_transformation, postcode_parse
from io_utils import copy_directory_contents, create_folder, read_space_path, write_space_path
from updater import UpdateManager, VersionCheckError


def prompt_update(version_info: str) -> bool:
    """User confirmation dialog with rich formatting"""
    return questionary.confirm(f"🎯 {version_info}\n🔧 Install update now?", default=True, auto_enter=False).ask()


def guided_option_entry() -> Tuple[str, str, str, Set[str]]:
    """Guide user through interactive parameter collection.

    Returns:
        Tuple containing:
        - space_path (str): Path to Google Drive directory
        - event_location (str): Location name for the event
        - event_date (str): Formatted as MonthYear (e.g. 'April2025')
        - postcode_districts (Set[str]): Set of cleaned postcode districts
    """
    space_path = read_space_path()
    if not os.path.isdir(space_path):
        space_path = questionary.path("📁 What is the path to the SeedSower's Google Drive space?").ask()

    event_location = questionary.text(
        "📍 What is the Seedsower's event location (e.g. Antrim, Dumfries, Exeter?)"
    ).ask()

    month_choices = _get_month_choices()
    event_date = questionary.select("📅 When is the Seedsower's event planned to happen?", choices=month_choices).ask()

    districts_input = questionary.text(
        "✉️ Enter all postcode districts to be extracted (separate them with commas e.g CV1,CV5):"
    ).ask()
    districts = {district.strip() for district in districts_input.split(",") if district.strip()}

    return (space_path, event_location, event_date, districts)


def _get_month_choices(num_months: int = 12) -> List[str]:
    """Generate month-year options for event planning.

    Args:
        num_months: Number of future months to generate (default: 12)

    Returns:
        List of formatted MonthYear strings (e.g. ['April2025', 'May2025'])
    """
    today = datetime.today()
    current_month = today.month
    current_year = today.year

    months_and_years = []
    for i in range(num_months):
        month = (current_month + i - 1) % 12 + 1
        year = current_year + (current_month + i - 1) // 12
        months_and_years.append(f"{calendar.month_name[month]}{year}")

    return months_and_years


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
            python script.py manual -s "C:/Google Drive/SeedSower" -e Belfast -d April2025 -p BT1 BT2
            python script.py manual --space_path "~/SeedSower" --event_location Derry \\
                --event_date May2025 --postcode_districts BT48 BT49""",
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
        "-d", "--event_date", required=True, help='Event date in MonthYear format (e.g. "April2025")'
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


if __name__ == "__main__":
    create_folder(SystemDefs.BASE_DIRECTORY)
    logger = create_logger(file_append=False)

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

    atexit.register(input, "Press Enter to exit...")

    args = parse_arguments()
    if args.mode == "guided":
        space_path, event_location, event_date, postcode_districts = guided_option_entry()
    elif args.mode == "manual":
        space_path, event_location, event_date, postcode_districts = (
            args.space_path,
            args.event_location,
            args.event_date,
            set(args.postcode_districts),
        )

    write_space_path(space_path)

    event_path = os.path.join(space_path, SystemDefs.EVENTS_FOLDER_NAME, f"{event_location}_{event_date}")
    logger.info(f"Event path: {event_path}")
    if os.path.isdir(event_path):
        logger.error(f"Failure: The event folder '{event_path}' already exists.")
        sys.exit(1)

    create_folder(event_path)
    create_folder(os.path.join(event_path, "Output"))

    qgis_template_folder_path = os.path.join(space_path, SystemDefs.QGIS_TEMPLATE_FOLDER_NAME)
    copy_directory_contents(qgis_template_folder_path, event_path)
    qgis_file_path = os.path.join(event_path, "Template.qgz")
    new_qgis_file_path = os.path.join(event_path, f"{event_location}.qgz")
    os.rename(qgis_file_path, new_qgis_file_path)

    data_folder_path = os.path.join(space_path, SystemDefs.DATA_FOLDER_NAME)
    paf_file_path, ons_data_path = data_transformation(data_folder_path, postcode_districts)
    postcode_parse(paf_file_path, ons_data_path, postcode_districts, event_path)

    os.startfile(event_path)
