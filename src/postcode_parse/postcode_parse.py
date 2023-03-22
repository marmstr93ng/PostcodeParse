import csv
import re
import argparse
import simplekml
import os

from sys import exit
from tqdm import tqdm

paf_format = {
    "Organisation Name": 0,
    "Department Name": 1,
    "PO Box": 2,
    "Building Name": 3,
    "Sub-Building Name": 4,
    "Building Number": 5,
    "Thoroughfare": 6,
    "Street": 7,
    "Double Dependent Locality": 8,
    "Dependent Locality": 9,
    "Post Town": 10,
    "Postcode": 11,
    "Postcode Type": 12,
    "DPS": 13
}

ons_format = {
    "Postcode": 2,
    "Latitude": 42,
    "Longitude": 43
}


class PostcodeData(object):
    def __init__(self, latitude, longitude):
        self.address_count = 1
        self.latitude = latitude
        self.longitude = longitude


def postcode_parse(data_file_path, desired_postcode_district, ons_data_path, csv_flag, kml_flag):
    postcode_output_dict = {}
    ons_data = open_ons_data(ons_data_path)

    with open(data_file_path) as csv_file:
        lines = [line for line in csv_file]
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)

        for row in tqdm(csv_reader, total=len(lines)):
            if is_not_business_paf(row) and is_small_postcode_type_paf(row):
                if is_desired_postcode_district(row[paf_format["Postcode"]], desired_postcode_district):
                    postcode = row[paf_format["Postcode"]]
                    if postcode not in postcode_output_dict:
                        latitude, longitude = retrieve_coords_ons(ons_data, postcode)
                        postcode_output_dict[postcode] = PostcodeData(latitude, longitude)
                    else:
                        postcode_output_dict[postcode].address_count += 1

    output_dir = os.path.join(os.getcwd(), "output")
    create_folder(output_dir)
    if csv_flag:
        csv_output(postcode_output_dict, os.path.join(output_dir, f"{desired_postcode_district} Postcodes.csv"))
    if kml_flag:
        kml_output(postcode_output_dict, os.path.join(output_dir, f"{desired_postcode_district} Postcodes.kml"))


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
        return True if postcode_district == desired_postcode_district else False


def open_ons_data(ons_data_path):
    with open(ons_data_path) as csv_file:
        lines = [line for line in csv_file]
        csv_reader = csv.reader(lines, delimiter=",")

        ignore_header(csv_reader)
    return csv_reader


def retrieve_coords_ons(ons_data, postcode):
    for row in ons_data:
        if row[ons_format["Postcode"]] == postcode:
            return row[ons_format["Latitude"]], row[ons_format["Longitude"]]


def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def csv_output(postcode_output_dict, output_path):
    with open(output_path, mode="w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["postcode", "address count", "latitude", "longitude"])

        writer.writeheader()
        for postcode, postcode_data in postcode_output_dict.items():
            writer.writerow({
                "postcode": postcode,
                "address count": postcode_data.address_count,
                "latitude": postcode_data.latitude,
                "longitude": postcode_data.longitude
            })


def kml_output(postcode_output_dict, output_path):
    kml = simplekml.Kml()

    for postcode, postcode_data in postcode_output_dict.items():
        pnt = kml.newpoint()
        pnt.name = postcode
        pnt.extendeddata.newdata(name="AddressCount", value=postcode_data.address_count, displayname=None)
        pnt.coords = [(postcode_data.longitude, postcode_data.latitude)]

    kml.save(output_path)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Parse Postcodes")
    parser.add_argument("-f", "--file", required=True, help="path to paf source file")
    parser.add_argument("-p", "--postcode", required=True, help="postcode to parse for")
    parser.add_argument("-d", "--data", required=True, help="path to ons postcode data csv")
    parser.add_argument("-c", "--csv_flag", action='store_true', help="write output to csv")
    parser.add_argument("-k", "--kml_flag", action='store_true', help="write output to kml")

    args = parser.parse_args()

    postcode_parse(args.file, args.postcode, args.data, args.csv_flag, args.kml_flag)
