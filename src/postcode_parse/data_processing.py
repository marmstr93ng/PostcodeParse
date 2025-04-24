import csv
import logging
import os
import re
from typing import Dict, List, Set, Tuple, Union

from _constants import PostcodeData, SystemDefs
from io_utils import get_file_length
from output import create_postcode_info_txt, csv_output, kml_output
from tqdm import tqdm

logger = logging.getLogger(__name__)


def data_transformation(data_folder_path: str, desired_postcode_districts: Set[str]) -> Tuple[str, str]:
    """Process PAF and ONS data files to extract relevant postcode districts.

    Args:
        data_folder_path: Path to directory containing input data files
        desired_postcode_districts: Set of postcode districts to filter for

    Returns:
        Tuple of (processed PAF file path, processed ONS file path)

    Raises:
        Exception: If ONS file for specified postcode district cannot be found
    """
    paf_file_path = os.path.join(data_folder_path, SystemDefs.PAF_FILE_NAME)
    final_paf_path = _trim_file(
        paf_file_path, desired_postcode_districts, SystemDefs.PAF_FORMAT["Postcode"], SystemDefs.TEMP_PAF_CSV
    )

    ons_folder_path = os.path.join(data_folder_path, SystemDefs.ONS_FOLDER_NAME)
    ons_file_path = _find_ons_file(ons_folder_path, list(desired_postcode_districts)[0])
    final_ons_path = _trim_file(
        ons_file_path, desired_postcode_districts, SystemDefs.ONS_FORMAT["Postcode"], SystemDefs.TEMP_ONS_CSV
    )

    return (final_paf_path, final_ons_path)


def _find_ons_file(ons_folder_path: str, outward_code: str) -> str:
    """Locate the appropriate ONS postcode file for the given outward code.

    Args:
        ons_folder_path: Path to ONS data directory
        outward_code: Initial part of postcode (e.g., 'BT1')

    Returns:
        Full path to matching ONS CSV file

    Raises:
        Exception: If no matching file found
    """
    outward_code_letters = re.sub(r"\d", "", outward_code)

    ons_files = os.listdir(ons_folder_path)
    for ons_file in ons_files:
        if ons_file.startswith(f"{SystemDefs.ONS_FOLDER_NAME}_UK_") and ons_file.endswith(".csv"):
            ons_file_outward_code = os.path.splitext(ons_file)[0].split("_")[-1]

            if outward_code_letters == ons_file_outward_code:
                return os.path.join(ons_folder_path, ons_file)
    raise Exception(f"ONS file for {outward_code} couldn't be found in {ons_folder_path}")


def _trim_file(data_path: str, desired_postcode_districts: Set[str], postcode_index: int, output_path: str) -> str:
    """Filter CSV file to only include rows from specified postcode districts.

    Args:
        data_path: Path to input CSV file
        desired_postcode_districts: Set of postcode districts to include
        postcode_index: Column index containing postcode data
        output_path: Path for filtered output file

    Returns:
        Path to the created output file
    """
    total_rows = get_file_length(data_path)

    with open(data_path, newline="") as input_file, open(output_path, "w", newline="") as output_file:
        csv_reader = csv.reader(input_file)
        csv_writer = csv.writer(output_file)

        for row in tqdm(csv_reader, total=total_rows, desc=f"Trimming {data_path}"):
            if _is_desired_postcode_district(row[postcode_index], desired_postcode_districts):
                csv_writer.writerow(row)

    return output_path


def postcode_parse(
    paf_file_path: str, ons_data_path: str, desired_postcode_districts: Set[str], output_path: str
) -> None:
    """Main function to process postcode data and generate outputs.

    Args:
        paf_file_path: Path to processed PAF CSV file
        ons_data_path: Path to processed ONS CSV file
        desired_postcode_districts: Set of postcode districts being processed
        output_path: Directory path for output files
    """
    postcode_output_dict, unlocated_postcodes = _process_paf_file(
        paf_file_path, desired_postcode_districts, ons_data_path
    )
    _generate_outputs(postcode_output_dict, unlocated_postcodes, desired_postcode_districts, output_path)


def _process_paf_file(
    paf_file_path: str, desired_postcode_districts: Set[str], ons_data_path: str
) -> Tuple[Dict[str, PostcodeData], Dict[str, int]]:
    """Process PAF file and return processed data.

    Args:
        paf_file_path: Path to PAF CSV file
        desired_postcode_districts: Set of postcode districts to process
        ons_data_path: Path to ONS coordinate data file

    Returns:
        Tuple containing:
        - Dictionary of postcodes to PostcodeData objects
        - Dictionary of unlocated postcode counts
    """
    postcode_output_dict: Dict[str, PostcodeData] = {}
    unlocated_postcodes: Dict[str, int] = {}
    paf_data_length = get_file_length(paf_file_path)

    with open(paf_file_path, newline="") as paf_file:
        paf_data_reader = csv.reader(paf_file)
        for row in tqdm(paf_data_reader, total=paf_data_length, desc="Processing PAF data"):
            _process_paf_row(row, desired_postcode_districts, postcode_output_dict, unlocated_postcodes, ons_data_path)

    return postcode_output_dict, unlocated_postcodes


def _process_paf_row(
    row: List[str],
    desired_postcode_districts: Set[str],
    postcode_output_dict: Dict[str, PostcodeData],
    unlocated_postcodes: Dict[str, int],
    ons_data_path: str,
) -> None:
    """Process individual PAF row and update data structures.

    Args:
        row: CSV row data from PAF file
        desired_postcode_districts: Set of postcode districts to process
        postcode_output_dict: Dictionary to store valid postcode data
        unlocated_postcodes: Dictionary to track missing coordinates
        ons_data_path: Path to ONS coordinate data file
    """
    postcode = row[SystemDefs.PAF_FORMAT["Postcode"]]
    logger.debug(f"Postcode: {postcode}")

    if not _is_valid_paf_row(row, postcode, desired_postcode_districts):
        logger.debug(f"{postcode} is NOT a desired address.")
        return

    _update_postcode_data(postcode, postcode_output_dict, unlocated_postcodes, ons_data_path)


def _is_valid_paf_row(row: List[str], postcode: str, desired_postcode_districts: Set[str]) -> bool:
    """Check if PAF row meets criteria for processing.

    Args:
        row: CSV row data from PAF file
        postcode: Extracted postcode from row
        desired_postcode_districts: Set of target postcode districts

    Returns:
        True if row should be processed, False otherwise
    """
    is_not_business_flag = row[SystemDefs.PAF_FORMAT["Organisation Name"]] == ""
    is_small_postcode_flag = row[SystemDefs.PAF_FORMAT["Postcode Type"]] == "S"
    return (
        is_not_business_flag
        and is_small_postcode_flag
        and _is_desired_postcode_district(postcode, desired_postcode_districts)
    )


def _update_postcode_data(
    postcode: str,
    postcode_output_dict: Dict[str, PostcodeData],
    unlocated_postcodes: Dict[str, int],
    ons_data_path: str,
) -> None:
    """Update postcode data structures with new information.

    Args:
        postcode: Postcode being processed
        postcode_output_dict: Dictionary to store valid postcode data
        unlocated_postcodes: Dictionary to track missing coordinates
        ons_data_path: Path to ONS coordinate data file
    """
    if postcode in postcode_output_dict:
        postcode_output_dict[postcode].address_count += 1
        logger.debug(f"{postcode} exists. Count = {postcode_output_dict[postcode].address_count}")
    else:
        logger.debug(f"{postcode} is new")
        _add_new_postcode(postcode, postcode_output_dict, unlocated_postcodes, ons_data_path)


def _add_new_postcode(
    postcode: str,
    postcode_output_dict: Dict[str, PostcodeData],
    unlocated_postcodes: Dict[str, int],
    ons_data_path: str,
) -> None:
    """Add new postcode entry with coordinates if available.

    Args:
        postcode: New postcode to add
        postcode_output_dict: Dictionary to store valid postcode data
        unlocated_postcodes: Dictionary to track missing coordinates
        ons_data_path: Path to ONS coordinate data file
    """
    latitude, longitude = _retrieve_coords_ons(ons_data_path, postcode)
    logger.debug(f"{postcode} coords: Latitude = {latitude} Longitude = {longitude}")

    if latitude is None or longitude is None:
        logger.debug(f"{postcode} is not located.")
        unlocated_postcodes = _add_to_unlocated_postcodes(postcode, unlocated_postcodes)
    else:
        postcode_output_dict[postcode] = PostcodeData(latitude, longitude)
        logger.debug(f"{postcode} added to dictionary: {postcode_output_dict.keys()}")


def _generate_outputs(
    postcode_output_dict: Dict[str, PostcodeData],
    unlocated_postcodes: Dict[str, int],
    desired_postcode_districts: Set[str],
    output_path: str,
) -> None:
    """Generate all output files and logs.

    Args:
        postcode_output_dict: Dictionary of valid postcode data
        unlocated_postcodes: Dictionary of missing coordinate counts
        desired_postcode_districts: Set of processed postcode districts
        output_path: Directory path for output files
    """
    csv_output(postcode_output_dict, os.path.join(output_path, "Postcodes.csv"))
    kml_output(postcode_output_dict, os.path.join(output_path, "Postcodes.kml"))
    create_postcode_info_txt(output_path, desired_postcode_districts)
    logger.info(unlocated_postcodes)


def _is_desired_postcode_district(data: str, desired_postcode_districts: Set[str]) -> bool:
    """Check if a postcode string matches any of the desired postcode districts.

    Args:
        data: String containing postcode data to check.
        desired_postcode_districts: Set of valid postcode districts (case-sensitive).

    Returns:
        bool: True if the postcode district is found in the desired set, False otherwise.
    """
    match = SystemDefs.POSTCODE_DISTRICT_PATTERN.match(data)
    if match:
        postcode_district = match.group(1)
        return postcode_district in desired_postcode_districts
    return False


def _retrieve_coords_ons(ons_data_path: str, postcode: str) -> Tuple[Union[str, None], Union[str, None]]:
    """Retrieve latitude and longitude coordinates for a postcode from ONS CSV data.

    Args:
        ons_data_path: Path to ONS-formatted CSV file containing postcode coordinates.
        postcode: Full postcode to search for (case-sensitive).

    Returns:
        Tuple containing (latitude, longitude) as strings if found, (None, None) otherwise.

    Note:
        CSV format requires specific column indices defined in SystemDefs.ONS_FORMAT.
    """
    with open(ons_data_path, newline="") as file:
        csv_reader = csv.reader(file)

        for row in csv_reader:
            if row[SystemDefs.ONS_FORMAT["Postcode"]] == postcode:
                return row[SystemDefs.ONS_FORMAT["Latitude"]], row[SystemDefs.ONS_FORMAT["Longitude"]]

    return None, None


def _add_to_unlocated_postcodes(postcode: str, unlocated_postcodes: Dict[str, int]) -> Dict[str, int]:
    """Increment counter for unlocated postcodes in tracking dictionary.

    Args:
        postcode: Postcode that failed geolocation.
        unlocated_postcodes: Dictionary tracking postcodes and their occurrence counts.

    Returns:
        Updated dictionary with incremented count for the specified postcode.

    Note:
        Modifies the input dictionary in place while also returning it.
        Logs debug messages for count changes.
    """
    if postcode in unlocated_postcodes:
        unlocated_postcodes[postcode] += 1
        logger.debug(f"Adding 1 to {postcode} in unlocated postcodes dictionary: {unlocated_postcodes}")
    else:
        logger.debug(f"{postcode} in not in unlocated postcodes dictionary: {unlocated_postcodes}")
        unlocated_postcodes[postcode] = 1
    return unlocated_postcodes
