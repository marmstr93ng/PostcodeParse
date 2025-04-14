import argparse
import atexit
import csv
import os
import re
import shutil
import sys
from datetime import datetime
from typing import Dict, Set, Tuple, Union

import questionary
import simplekml
import yaml
from _constants import PostcodeData, SystemDefs
from _log import create_logger
from tqdm import tqdm


def create_folder(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def guided_option_entry() -> Tuple[str, str, Set[str]]:
    space_path = read_space_path()
    if not os.path.isdir(space_path):
        space_path = questionary.path("What is the path to the SeedSower's Google Drive space?").ask()

    event_location = questionary.text("What is the Seedsower's event location (e.g. Antrim, Dumfries, Exeter?)").ask()

    districts_input = questionary.text(
        "Enter all postcode districts to extract (separate them with commas e.g CV1,CV5):"
    ).ask()
    districts = {district.strip() for district in districts_input.split(",") if district.strip()}

    return (space_path, event_location, districts)


def read_space_path() -> str:
    try:
        with open(SystemDefs.SETTINGS_FILE) as file:
            settings = yaml.safe_load(file)
            return settings.get("space_path", "")
    except FileNotFoundError:
        return ""


def write_space_path(path: str) -> None:
    settings = {"space_path": path}
    with open(SystemDefs.SETTINGS_FILE, "w") as file:
        yaml.dump(settings, file)


def data_transformation(data_folder_path: str, desired_postcode_districts: Set[str]) -> Tuple[str, str]:
    paf_file_path = os.path.join(data_folder_path, SystemDefs.PAF_FILE_NAME)
    final_paf_path = trim_file(
        paf_file_path, desired_postcode_districts, SystemDefs.PAF_FORMAT["Postcode"], SystemDefs.TEMP_PAF_CSV
    )

    ons_folder_path = os.path.join(data_folder_path, SystemDefs.ONS_FOLDER_NAME)
    ons_file_path = find_ons_file(ons_folder_path, list(desired_postcode_districts)[0])
    final_ons_path = trim_file(
        ons_file_path, desired_postcode_districts, SystemDefs.ONS_FORMAT["Postcode"], SystemDefs.TEMP_ONS_CSV
    )

    return (final_paf_path, final_ons_path)


def find_ons_file(ons_folder_path: str, outward_code: str) -> str:
    outward_code_letters = re.sub(r"\d", "", outward_code)

    ons_files = os.listdir(ons_folder_path)
    for ons_file in ons_files:
        if ons_file.startswith(f"{SystemDefs.ONS_FOLDER_NAME}_UK_") and ons_file.endswith(".csv"):
            ons_file_outward_code = os.path.splitext(ons_file)[0].split("_")[-1]

            if outward_code_letters == ons_file_outward_code:
                return os.path.join(ons_folder_path, ons_file)
    raise Exception(f"ONS file for {outward_code} couldn't be found in {ons_folder_path}")


def trim_file(data_path: str, desired_postcode_districts: Set[str], postcode_index: int, output_path: str) -> str:
    total_rows = get_file_length(data_path)

    with open(data_path, newline="") as input_file, open(output_path, "w", newline="") as output_file:
        csv_reader = csv.reader(input_file)
        csv_writer = csv.writer(output_file)

        for row in tqdm(csv_reader, total=total_rows, desc=f"Trimming {data_path}"):
            if is_desired_postcode_district(row[postcode_index], desired_postcode_districts):
                csv_writer.writerow(row)

    return output_path


def postcode_parse(
    paf_file_path: str, ons_data_path: str, desired_postcode_districts: Set[str], output_path: str
) -> None:
    postcode_output_dict: Dict[str, PostcodeData] = {}
    unlocated_postcodes: Dict[str, int] = {}

    paf_data_length = get_file_length(paf_file_path)

    with open(paf_file_path, newline="") as paf_file:
        paf_data_reader = csv.reader(paf_file)

        for row in tqdm(paf_data_reader, total=paf_data_length):
            postcode = row[SystemDefs.PAF_FORMAT["Postcode"]]
            logger.debug(f"Postcode: {postcode}")

            is_not_business_flag = row[SystemDefs.PAF_FORMAT["Organisation Name"]] == ""
            is_small_postcode_flag = row[SystemDefs.PAF_FORMAT["Postcode Type"]] == "S"
            is_desired_postcode_district_flag = is_desired_postcode_district(postcode, desired_postcode_districts)
            if is_not_business_flag and is_small_postcode_flag and is_desired_postcode_district_flag:
                if postcode in postcode_output_dict:
                    postcode_output_dict[postcode].address_count += 1
                    logger.debug(f"{postcode} already exists. Count = {postcode_output_dict[postcode].address_count}")
                else:
                    logger.debug(f"{postcode} is new")
                    latitude, longitude = retrieve_coords_ons(ons_data_path, postcode)
                    logger.debug(f"{postcode} coords: Latitude = {latitude} Longitude = {longitude}")

                    if latitude is None or longitude is None:
                        logger.debug(f"{postcode} is not located.")
                        unlocated_postcodes = add_to_unlocated_postcodes(postcode, unlocated_postcodes)
                    else:
                        postcode_output_dict[postcode] = PostcodeData(latitude, longitude)
                        logger.debug(f"{postcode} added to the dictionary: {postcode_output_dict.keys()}")
            else:
                logger.debug(f"{postcode} is NOT a desired address.")

    csv_output(postcode_output_dict, os.path.join(output_path, "Postcodes.csv"))
    kml_output(postcode_output_dict, os.path.join(output_path, "Postcodes.kml"))
    create_postcode_info_txt(output_path, desired_postcode_districts)
    logger.info(unlocated_postcodes)


def get_file_length(file_path: str) -> int:
    logger.info(f"Getting file length for {file_path}")
    with open(file_path, newline="") as file:
        return sum(1 for _ in file)


def is_desired_postcode_district(data: str, desired_postcode_districts: Set[str]) -> bool:
    match = SystemDefs.POSTCODE_DISTRICT_PATTERN.match(data)
    if match:
        postcode_district = match.group(1)
        return postcode_district in desired_postcode_districts
    return False


def retrieve_coords_ons(ons_data_path: str, postcode: str) -> Tuple[Union[str, None], Union[str, None]]:
    with open(ons_data_path, newline="") as file:
        csv_reader = csv.reader(file)

        for row in csv_reader:
            if row[SystemDefs.ONS_FORMAT["Postcode"]] == postcode:
                return row[SystemDefs.ONS_FORMAT["Latitude"]], row[SystemDefs.ONS_FORMAT["Longitude"]]

    return None, None


def add_to_unlocated_postcodes(postcode: str, unlocated_postcodes: Dict[str, int]) -> Dict[str, int]:
    if postcode in unlocated_postcodes:
        unlocated_postcodes[postcode] += 1
        logger.debug(f"Adding 1 to {postcode} in unlocated postcodes dictionary: {unlocated_postcodes}")
    else:
        logger.debug(f"{postcode} in not in unlocated postcodes dictionary: {unlocated_postcodes}")
        unlocated_postcodes[postcode] = 1
    return unlocated_postcodes


def csv_output(postcode_output_dict: Dict[str, PostcodeData], output_path: str) -> None:
    with open(output_path, mode="w", newline="") as csv_file:
        logger.debug(f"Writing CSV to {output_path}")
        writer = csv.DictWriter(csv_file, fieldnames=["postcode", "address count", "latitude", "longitude"])

        writer.writeheader()
        for postcode, postcode_data in postcode_output_dict.items():
            writer.writerow(
                {
                    "postcode": postcode,
                    "address count": postcode_data.address_count,
                    "latitude": postcode_data.latitude,
                    "longitude": postcode_data.longitude,
                }
            )


def kml_output(postcode_output_dict: Dict[str, PostcodeData], output_path: str) -> None:
    kml = simplekml.Kml()
    logger.debug(f"Writing KML to {output_path}")

    for postcode, postcode_data in postcode_output_dict.items():
        pnt = kml.newpoint()
        pnt.name = postcode
        pnt.extendeddata.newdata(name="AddressCount", value=postcode_data.address_count, displayname=None)
        pnt.coords = [(postcode_data.longitude, postcode_data.latitude)]

    kml.save(output_path)


def create_postcode_info_txt(output_path: str, desired_postcode_districts: Set[str]) -> None:
    path_without_ext = os.path.join(output_path, f"{''.join(desired_postcode_districts)} Postcodes")
    open(f"{path_without_ext}.txt", "w").close()


def copy_directory_contents(source_dir: str, destination_dir: str) -> None:
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


if __name__ == "__main__":
    atexit.register(input, "Press Enter to exit...")
    create_folder(SystemDefs.BASE_DIRECTORY)
    logger = create_logger(file_append=False)

    parser = argparse.ArgumentParser(description="Parse Postcodes")
    subparsers = parser.add_subparsers(title="Mode", dest="mode", help="Select the run mode of the script")

    guided_parser = subparsers.add_parser("guided", help="guide the user through the script option entry")

    manual_parser = subparsers.add_parser("manual", help="manually enter the script options")
    manual_parser.add_argument("-s", "--space_path", required=True, help="path to Seedsower's Google Drive space")
    manual_parser.add_argument(
        "-e", "--event_location", nargs="+", required=True, help="name of the Seedsower's event location"
    )
    manual_parser.add_argument("-d", "--districts", nargs="+", required=True, help="postcode districts to extract")

    parser.set_defaults(mode="guided")
    args = parser.parse_args()
    if args.mode == "guided":
        space_path, event_location, districts = guided_option_entry()
    elif args.mode == "manual":
        space_path, event_location, districts = args.space_path, args.event_location, set(args.districts)

    write_space_path(space_path)

    events_folder_path = os.path.join(space_path, SystemDefs.EVENTS_FOLDER_NAME)
    current_date = datetime.now()
    month_year = current_date.strftime("%B%Y")
    event_location_with_date = f"{event_location}_{month_year}"
    event_path = os.path.join(events_folder_path, event_location_with_date)
    logger.info(f"Event path: {event_path}")
    if os.path.isdir(event_path):
        logger.error(f"Failure: The event folder '{event_path}' already exists.")
        sys.exit(1)

    create_folder(event_path)
    create_folder(os.path.join(event_path, "Output"))

    data_folder_path = os.path.join(space_path, SystemDefs.DATA_FOLDER_NAME)
    paf_file_path, ons_data_path = data_transformation(data_folder_path, districts)

    postcode_parse(paf_file_path, ons_data_path, districts, event_path)

    qgis_template_folder_path = os.path.join(space_path, SystemDefs.QGIS_TEMPLATE_FOLDER_NAME)
    copy_directory_contents(qgis_template_folder_path, event_path)
    qgis_file_path = os.path.join(event_path, "Template.qgz")
    new_qgis_file_path = os.path.join(event_path, f"{event_location}.qgz")
    os.rename(qgis_file_path, new_qgis_file_path)

    os.startfile(event_path)
