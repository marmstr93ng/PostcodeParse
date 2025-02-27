import argparse
import atexit
import csv
import os
import re
from sys import exit
from typing import Dict, Iterator, List, Tuple, Union

import questionary
import simplekml
from _constants import PostcodeData, SystemDefs
from _log import create_logger
from tqdm import tqdm


def postcode_parse(
    paf_file_path: str,
    desired_postcode_districts: List[str],
    ons_data_path: str,
) -> None:
    postcode_output_dict: Dict[str, PostcodeData] = {}
    unlocated_postcodes: Dict[str, int] = {}

    trim_ons_file(ons_data_path, desired_postcode_districts)

    paf_data_reader, paf_data_length = create_csv_reader(paf_file_path)
    for row in tqdm(paf_data_reader, total=paf_data_length):
        postcode = row[SystemDefs.PAF_FORMAT["Postcode"]]
        logger.debug(f"Postcode: {postcode}")

        if (
            is_not_business_paf(row)
            and is_small_postcode_type_paf(row)
            and is_desired_postcode_district(postcode, desired_postcode_districts)
        ):
            if postcode in postcode_output_dict:
                postcode_output_dict[postcode].address_count += 1
                logger.debug(f"{postcode} already exists. Count = {postcode_output_dict[postcode].address_count}")
            else:
                logger.debug(f"{postcode} is new")
                latitude, longitude = retrieve_coords_ons(SystemDefs.TEMP_ONS_CSV, postcode)
                logger.debug(f"{postcode} coords: Latitude = {latitude} Longitude = {longitude}")

                if is_postcode_not_located(latitude, longitude):
                    logger.debug(f"{postcode} is not located.")
                    unlocated_postcodes = add_to_unlocated_postcodes(postcode, unlocated_postcodes)
                else:
                    postcode_output_dict[postcode] = PostcodeData(latitude, longitude)
                    logger.debug(f"{postcode} added to the dictionary: {postcode_output_dict.keys()}")
        else:
            logger.debug(f"{postcode} is NOT a desired address.")

    create_folder(SystemDefs.OUTPUT_DIRECTORY)
    path_without_ext = os.path.join(SystemDefs.OUTPUT_DIRECTORY, f"{'-'.join(desired_postcode_districts)} Postcodes")
    csv_output(postcode_output_dict, f"{path_without_ext}.csv")
    kml_output(postcode_output_dict, f"{path_without_ext}.kml")
    logger.info(unlocated_postcodes)


def trim_ons_file(ons_data_path: str, desired_postcode_districts: List[str]) -> None:
    create_folder(SystemDefs.TEMP_DIRECTORY)
    with open(SystemDefs.TEMP_ONS_CSV, mode="w", newline="") as tmp_ons_csv:
        logger.debug(f"Creating tmp ONS CSV file at {SystemDefs.TEMP_ONS_CSV}")
        csv_writer = csv.writer(tmp_ons_csv)
        ons_data_reader, _ = create_csv_reader(ons_data_path, ignore_header_flag=False)
        for index, row in enumerate(ons_data_reader):
            if index == 0 or is_desired_postcode_district(
                row[SystemDefs.ONS_FORMAT["Postcode"]], desired_postcode_districts
            ):
                csv_writer.writerow(row)


def ignore_header(reader_obj: Iterator[List[str]]) -> None:
    next(reader_obj)


def is_not_business_paf(data: list[str]) -> bool:
    is_not_business_flag = data[SystemDefs.PAF_FORMAT["Organisation Name"]] == ""
    logger.debug(f"Is Not A Business: {is_not_business_flag}")
    return is_not_business_flag


def is_small_postcode_type_paf(data: List[str]) -> bool:
    is_small_postcode = data[SystemDefs.PAF_FORMAT["Postcode Type"]] == "S"
    logger.debug(f"Is A Small Postcode: {is_small_postcode}")
    return is_small_postcode


def is_desired_postcode_district(data: str, desired_postcode_districts: List[str]) -> bool:
    postcode_district_match = re.match("^([A-Z]{1,2}[0-9]{1,2})", data)
    if postcode_district_match is not None:
        postcode_district = postcode_district_match.group(1)
    else:
        logger.error("ERROR: No postcode area match found!")
        exit(1)

    is_desired_postcode = postcode_district in desired_postcode_districts
    logger.debug(f"{postcode_district} is in {desired_postcode_districts}: {is_desired_postcode}")

    return is_desired_postcode


def is_postcode_not_located(latitude: Union[str, None], longitude: Union[str, None]) -> bool:
    return latitude is None or longitude is None


def add_to_unlocated_postcodes(postcode: str, unlocated_postcodes: Dict[str, int]) -> Dict[str, int]:
    if postcode in unlocated_postcodes:
        unlocated_postcodes[postcode] += 1
        logger.debug(f"Adding 1 to {postcode} in unlocated postcodes dictionary: {unlocated_postcodes}")
    else:
        logger.debug(f"{postcode} in not in unlocated postcodes dictionary: {unlocated_postcodes}")
        unlocated_postcodes[postcode] = 1
    return unlocated_postcodes


def create_csv_reader(csv_path: str, ignore_header_flag: bool = True) -> Tuple[Iterator[List[str]], int]:
    with open(csv_path) as csv_file:
        lines = list(csv_file)
        csv_reader = csv.reader(lines, delimiter=",")
        if ignore_header_flag:
            ignore_header(csv_reader)
    return csv_reader, len(lines)


def retrieve_coords_ons(ons_data_path: str, postcode: str) -> Tuple[Union[str, None], Union[str, None]]:
    ons_data_reader, _ = create_csv_reader(ons_data_path)
    for row in ons_data_reader:
        if row[SystemDefs.ONS_FORMAT["Postcode"]] == postcode:
            return row[SystemDefs.ONS_FORMAT["Latitude"]], row[SystemDefs.ONS_FORMAT["Longitude"]]

    return None, None


def create_folder(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


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


def guided_option_entry() -> Tuple[str, List[str], str, bool, bool, bool]:
    paf_path = questionary.path("What is the path to the PAF file?").ask()

    districts = []
    while True:
        districts.append(questionary.text("What postcode districts should be extracted?").ask())
        if not questionary.confirm("Add another district to extract?").ask():
            break

    ons_path = questionary.path("What is the path to the ONS Postcode File?").ask()
    return (paf_path, districts, ons_path)


if __name__ == "__main__":
    atexit.register(input, "Press Enter to exit...")
    create_folder(SystemDefs.TEMP_DIRECTORY)
    logger = create_logger(file_append=False)

    parser = argparse.ArgumentParser(description="Parse Postcodes")
    subparsers = parser.add_subparsers(title="Mode", dest="mode", help="Select the run mode of the script")

    guided_parser = subparsers.add_parser("guided", help="guide the user through the script option entry")

    manual_parser = subparsers.add_parser("manual", help="manually enter the script options")
    manual_parser.add_argument("-p", "--paf", required=True, help="path to paf file")
    manual_parser.add_argument("-d", "--districts", nargs="+", required=True, help="postcode districts to extract")
    manual_parser.add_argument("-o", "--ons", required=True, help="path to ons postcode data")

    parser.set_defaults(mode="guided")
    args = parser.parse_args()
    if args.mode == "guided":
        options = guided_option_entry()
    elif args.mode == "manual":
        options = (args.paf, args.districts, args.ons)

    postcode_parse(*options)
    os.startfile(SystemDefs.OUTPUT_DIRECTORY)
