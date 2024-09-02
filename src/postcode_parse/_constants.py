import os
from typing import Union


class SystemDefs:
    TEMP_FOLDER = os.getenv('TEMP')
    TEMP_DIRECTORY = os.path.join(TEMP_FOLDER, "PostcodeParser")
    LOGGING_FILE_PATH = os.path.join(TEMP_DIRECTORY, "log.log")

    TEMP_ONS_CSV = os.path.join(TEMP_DIRECTORY, "tmp_ons_data.csv")

    OUTPUT_DIRECTORY = os.path.join(TEMP_DIRECTORY, "output")

    PAF_FORMAT = {
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

    ONS_FORMAT = {"Postcode": 2, "Latitude": 42, "Longitude": 43}


class PostcodeData:
    def __init__(self, latitude: Union[str, None], longitude: Union[str, None]) -> None:
        self.address_count = 1
        self.latitude = latitude
        self.longitude = longitude
