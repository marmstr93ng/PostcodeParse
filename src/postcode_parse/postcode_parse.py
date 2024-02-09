import argparse
import csv
import os
import re
from sys import exit

import simplekml
from tqdm import tqdm

paf_format = {
    "Organisation Name": 11,
    "Department Name": 10,
    "PO Box": 9,
    "Building Name": 7,
    "Sub-Building Name": 8,
    "Building Number": 6,
    "Thoroughfare": 5,
    "Street": 4,
    "Double Dependent Locality": 3,
    "Dependent Locality": 2,
    "Post Town": 1,
    "Postcode": 0,
    "Postcode Type": 13,
    "DPS": 15,
}

ons_format = {"Postcode": 2, "Latitude": 42, "Longitude": 43}


class PostcodeData:
    def __init__(self, latitude, longitude):
        self.address_count = 1
        self.latitude = latitude
        self.longitude = longitude


def postcode_parse(data_file_path, desired_postcode_district, ons_data_path, csv_flag, kml_flag):
    postcode_output_dict = {}
    unlocated_postcodes = {}

    with open(data_file_path) as csv_file:
        lines = list(csv_file)
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)

        for row in tqdm(csv_reader, total=len(lines)):
            if (
                is_not_business_paf(row)
                and is_small_postcode_type_paf(row)
                and is_desired_postcode_district(row[paf_format["Postcode"]], desired_postcode_district)
            ):
                postcode = row[paf_format["Postcode"]]

                if postcode in postcode_output_dict:
                    postcode_output_dict[postcode].address_count += 1
                else:
                    latitude, longitude = retrieve_coords_ons(ons_data_path, postcode)
                    if is_postcode_not_located(latitude, longitude):
                        unlocated_postcodes = add_to_unlocated_postcodes(postcode, unlocated_postcodes)
                    else:
                        postcode_output_dict[postcode] = PostcodeData(latitude, longitude)

    output_dir = os.path.join(os.getcwd(), "output")
    create_folder(output_dir)
    path = os.path.join(output_dir, f"{'-'.join(desired_postcode_district)} Postcodes")
    if csv_flag:
        csv_output(postcode_output_dict, f"{path}.csv")
    if kml_flag:
        kml_output(postcode_output_dict, f"{path}.kml")
    print(unlocated_postcodes)


def ignore_header(reader_obj):
    next(reader_obj)


def is_not_business_paf(data):
    return data[paf_format["Organisation Name"]] == ""


def is_small_postcode_type_paf(data):
    return data[paf_format["Postcode Type"]] == "S"


def is_desired_postcode_district(data, desired_postcode_district):
    postcode_district_match = re.match("^([A-Z]{1,2}[0-9]{1,2})", data)
    try:
        postcode_district = postcode_district_match.group(1)
    except AttributeError:
        print("ERROR: No postcode area match found!")
        exit(1)
    else:
        return postcode_district in desired_postcode_district


def is_postcode_not_located(latitude, longitude):
    return latitude is None or longitude is None


def add_to_unlocated_postcodes(postcode, unlocated_postcodes):
    if postcode in unlocated_postcodes:
        unlocated_postcodes[postcode] += 1
    else:
        unlocated_postcodes[postcode] = 1
    return unlocated_postcodes


def open_ons_data(ons_data_path):
    with open(ons_data_path) as csv_file:
        lines = list(csv_file)
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)
    return csv_reader


def retrieve_coords_ons(ons_data_path, postcode):
    ons_data = open_ons_data(ons_data_path)
    for row in ons_data:
        if row[ons_format["Postcode"]] == postcode:
            return row[ons_format["Latitude"]], row[ons_format["Longitude"]]

    return None, None


def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def csv_output(postcode_output_dict, output_path):
    with open(output_path, mode="w", newline="") as csv_file:
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


def kml_output(postcode_output_dict, output_path):
    kml = simplekml.Kml()

    for postcode, postcode_data in postcode_output_dict.items():
        pnt = kml.newpoint()
        pnt.name = postcode
        pnt.extendeddata.newdata(name="AddressCount", value=postcode_data.address_count, displayname=None)
        pnt.coords = [(postcode_data.longitude, postcode_data.latitude)]

    kml.save(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse Postcodes")
    parser.add_argument("-f", "--file", required=True, help="path to paf source file")
    parser.add_argument("-p", "--postcode", nargs="+", required=True, help="postcodes to parse for")
    parser.add_argument("-d", "--data", required=True, help="path to ons postcode data csv")
    parser.add_argument("-c", "--csv_flag", action="store_true", help="write output to csv")
    parser.add_argument("-k", "--kml_flag", action="store_true", help="write output to kml")

    args = parser.parse_args()

    postcode_parse(args.file, args.postcode, args.data, args.csv_flag, args.kml_flag)
