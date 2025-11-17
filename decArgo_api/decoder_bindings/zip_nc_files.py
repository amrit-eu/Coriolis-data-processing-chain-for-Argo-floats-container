"""Code to Zip decoded NC files."""

import logging
import os
import traceback
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


class ZipNCFilesError(Exception):
    """Raised when there is an issue zipping the NC files."""


class ZipNCFiles:
    """Methods to zip newly decoded NC files from the Coriolis Decoder."""

    def __init__(self, wmonum: str):
        """Initialise the instance with the wmonum and NC file location."""
        self.wmonum = wmonum
        self.base_output_location = Path(os.getenv("OUTPUT_LOCATION", f"/mnt/data/output/nc/{wmonum}")).resolve()

    def zip_all_nc_files(self) -> BytesIO:
        """Zip all .nc files under the wmonum's output directory.

        Returns:
            A BytesIO object to make available for download.
        """
        try:
            buffer = BytesIO()

            with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as zipfile:
                for file in self.base_output_location.rglob("*.nc"):
                    zipfile.write(file)

            buffer.seek(0)
            return buffer
        except Exception as exc:
            logging.error("An error occured during the zip file process: %s", traceback.format_exc())
            raise ZipNCFilesError from exc
