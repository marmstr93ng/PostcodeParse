import argparse
import csv
import os
import re
from sys import exit
from typing import Dict, Iterator, List, Tuple, Union

import simplekml
from _constants import PostcodeData, SystemDefs
from _log import create_logger
from tqdm import tqdm


def postcode_parse(
    data_file_path: str, desired_postcode_district: str, ons_data_path: str, csv_flag: bool, kml_flag: bool
) -> None:
    postcode_output_dict: Dict[str, PostcodeData] = {}
    unlocated_postcodes: Dict[str, int] = {}

    with open(data_file_path) as csv_file:
        lines = list(csv_file)
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)

        for row in tqdm(csv_reader, total=len(lines)):
            postcode = row[SystemDefs.PAF_FORMAT["Postcode"]]
            logger.debug(f"Postcode: {postcode}")

            if (
                is_not_business_paf(row)
                and is_small_postcode_type_paf(row)
                and is_desired_postcode_district(postcode, desired_postcode_district)
            ):
                if postcode in postcode_output_dict:
                    postcode_output_dict[postcode].address_count += 1
                    logger.debug(f"{postcode} already exists. Count = {postcode_output_dict[postcode].address_count}")
                else:
                    logger.debug(f"{postcode} is new")
                    latitude, longitude = retrieve_coords_ons(ons_data_path, postcode)
                    logger.debug(f"{postcode} coords: Latitude = {latitude} Longitude = {longitude}")
                    if is_postcode_not_located(latitude, longitude):
                        logger.debug(f"{postcode} is not located.")
                        unlocated_postcodes = add_to_unlocated_postcodes(postcode, unlocated_postcodes)
                    else:
                        postcode_output_dict[postcode] = PostcodeData(latitude, longitude)
                        logger.debug(f"{postcode} added to the dictionary: {postcode_output_dict.keys()}")
            else:
                logger.debug(f"{postcode} is NOT a desired address.")

    output_dir = os.path.join(os.getcwd(), "output")
    create_folder(output_dir)
    path = os.path.join(output_dir, f"{'-'.join(desired_postcode_district)} Postcodes")
    if csv_flag:
        csv_output(postcode_output_dict, f"{path}.csv")
    if kml_flag:
        kml_output(postcode_output_dict, f"{path}.kml")
    print(unlocated_postcodes)


def ignore_header(reader_obj: Iterator[List[str]]) -> None:
    next(reader_obj)


def is_not_business_paf(data: list[str]) -> bool:
    is_not_business_flag = data[SystemDefs.PAF_FORMAT["Organisation Name"]] == ""
    logger.debug(f"Is Not A Business: {is_not_business_flag}")
    return is_not_business_flag


def is_small_postcode_type_paf(data: list[str]) -> bool:
    is_small_postcode = data[SystemDefs.PAF_FORMAT["Postcode Type"]] == "S"
    logger.debug(f"Is A Small Postcode: {is_small_postcode}")
    return is_small_postcode


def is_desired_postcode_district(data: str, desired_postcode_district: str) -> bool:
    postcode_district_match = re.match("^([A-Z]{1,2}[0-9]{1,2})", data)
    if postcode_district_match is not None:
        postcode_district = postcode_district_match.group(1)
    else:
        print("ERROR: No postcode area match found!")
        exit(1)

    is_desired_postcode = postcode_district in desired_postcode_district
    logger.debug(f"{postcode_district} is in {desired_postcode_district}: {is_desired_postcode}")

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


def open_ons_data(ons_data_path: str) -> Iterator[List[str]]:
    with open(ons_data_path) as csv_file:
        lines = list(csv_file)
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)
    return csv_reader


def retrieve_coords_ons(ons_data_path: str, postcode: str) -> Tuple[Union[str, None], Union[str, None]]:
    ons_data = open_ons_data(ons_data_path)
    for row in ons_data:
        if row[SystemDefs.ONS_FORMAT["Postcode"]] == postcode:
            return row[SystemDefs.ONS_FORMAT["Latitude"]], row[SystemDefs.ONS_FORMAT["Longitude"]]

    return None, None


def create_folder(path: str) -> None:
    if not os.path.exists(path):
        logger.debug(f"Creating folder at {path}")
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


if __name__ == "__main__":
    logger = create_logger(file_append=False)

    parser = argparse.ArgumentParser(description="Parse Postcodes")
    parser.add_argument("-f", "--file", required=True, help="path to paf source file")
    parser.add_argument("-p", "--postcode", nargs="+", required=True, help="postcodes to parse for")
    parser.add_argument("-d", "--data", required=True, help="path to ons postcode data csv")
    parser.add_argument("-c", "--csv_flag", action="store_true", help="write output to csv")
    parser.add_argument("-k", "--kml_flag", action="store_true", help="write output to kml")

    args = parser.parse_args()

    postcode_parse(args.file, args.postcode, args.data, args.csv_flag, args.kml_flag)
