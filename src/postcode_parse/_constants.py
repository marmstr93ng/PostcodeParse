import os
import re
from typing import Union


class SystemDefs:
    BASE_PATH = "C:\\Users\\Public\\Documents"
    BASE_DIRECTORY = os.path.join(BASE_PATH, "PostcodeParser")
    LOGGING_FILE_PATH = os.path.join(BASE_DIRECTORY, "log.log")
    SETTINGS_FILE = os.path.join(BASE_DIRECTORY, "settings.yml")

    GITHUB_REPO = "marmstr93ng/PostcodeParse"
    INSTALLER_NAME = "postcode_parse_installer.exe"

    EVENTS_FOLDER_NAME = "🛠️ Events"
    DATA_FOLDER_NAME = "🗂️ Data"
    TEMPLATES_FOLDER_NAME = "♻️ Templates"
    QGIS_TEMPLATE_FOLDER_NAME = os.path.join(TEMPLATES_FOLDER_NAME, "QGIS")
    PAF_FILE_NAME = "PAF.csv"
    ONS_FOLDER_NAME = "ONSPD_AUG_2024"

    TEMP_PAF_CSV = os.path.join(BASE_DIRECTORY, "tmp_paf_data.csv")
    TEMP_ONS_CSV = os.path.join(BASE_DIRECTORY, "tmp_ons_data.csv")

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

    ONS_FORMAT = {"Postcode": 2, "Latitude": 41, "Longitude": 42}

    POSTCODE_DISTRICT_PATTERN = re.compile(r"^([A-Z]{1,2}[0-9]{1,2})")


class PostcodeData:
    def __init__(self, latitude: Union[str, None], longitude: Union[str, None]) -> None:
        self.address_count = 1
        self.latitude = latitude
        self.longitude = longitude
