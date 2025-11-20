"""Utility to remove the files from the Iridium directory once processing is complete."""

import shutil
from pathlib import Path


class RemoveIridiumFiles:
    """Code to remove the iridium files once complete."""

    iridium_path = "/mnt/data/output/iridium/{}_{}"

    @classmethod
    def remove_iridium_files(cls, imei: str, wmonum: str) -> None:
        """Remove the imei/wmonum specific Iridium directory."""
        iridium_path = Path(cls.iridium_path.format(imei, wmonum))
        if iridium_path.is_dir():
            shutil.rmtree(iridium_path)
