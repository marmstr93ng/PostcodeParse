import os
from typing import Union


class SystemDefs:
    LOG_DIRECTORY = "logging"
    LOGGING_FILE_PATH = os.path.join(LOG_DIRECTORY, "log.log")
    os.makedirs(os.path.dirname(LOGGING_FILE_PATH), exist_ok=True)

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
