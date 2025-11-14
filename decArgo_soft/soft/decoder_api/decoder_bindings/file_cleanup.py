"""Code to clean up new NC files after the zip file has been produced."""

import logging
import os
import shutil
from pathlib import Path


class NCFileCleaner:
    """Methods to clean up NC files once processed."""
    def __init__(self, wmonum: str):
        """Initialise the file cleaner."""
        self.wmonum = wmonum
        self.base_output_location = Path(os.getenv("OUTPUT_LOCATION", "/mnt/data/output/nc/")).resolve()


    def remove_nc_directory(self) -> None:
        """Remove the newly produced NC file directory and its files."""
        if (nc_folder := self.base_output_location / self.wmonum).is_dir():
            shutil.rmtree(nc_folder)
            logging.info("Directory: %s, has been removed.")
