import csv
import logging
import os
from typing import Dict, Set

import simplekml
from _constants import PostcodeData

logger = logging.getLogger(__name__)


def create_postcode_info_txt(output_path: str, desired_postcode_districts: Set[str]) -> None:
    """Creates an empty text file named with the desired postcode districts.

    Args:
        output_path: Directory path where the file will be created
        desired_postcode_districts: Set of postcode district strings to include in filename
    """
    path_without_ext = os.path.join(output_path, f"{''.join(desired_postcode_districts)} Postcodes")
    open(f"{path_without_ext}.txt", "w").close()


def csv_output(postcode_output_dict: Dict[str, PostcodeData], output_path: str) -> None:
    """Generates a CSV file containing postcode geodata.

    Args:
        postcode_output_dict: Dictionary mapping postcodes to PostcodeData objects
        output_path: Full path including filename for output CSV file
    """
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
    """Generates a KML file containing postcode geodata with address count metadata.

    Args:
        postcode_output_dict: Dictionary mapping postcodes to PostcodeData objects
        output_path: Full path including filename for output KML file
    """
    kml = simplekml.Kml()
    logger.debug(f"Writing KML to {output_path}")

    for postcode, postcode_data in postcode_output_dict.items():
        pnt = kml.newpoint(name=postcode, coords=[(postcode_data.longitude, postcode_data.latitude)])
        pnt.extendeddata.newdata(name="AddressCount", value=postcode_data.address_count, displayname=None)

    kml.save(output_path)
