"""Decoder Bindings."""

import sys
from pathlib import Path
import os

import subprocess
from pydantic import BaseModel, field_validator


class EmptyInputDirectoryError(Exception):
    """Raised when the input directory is empty."""


class ExecutionError(Exception):
    """Raised when no wmonum is passed."""


class DecoderConfiguration(BaseModel):
    """Configuration used to pass to the decoder, with validation applied."""

    input_files_directory: Path
    output_files_directory: Path
    configuration_files_directory: Path

    @field_validator("input_files_directory", mode="before")
    def check_input_files_directory(cls, input_directory: Path):
        """Validate then resolve the input files directory."""
        if not input_directory.is_dir():
            raise ValueError(f"{input_directory} is not a valid input directory!")

        if not any(input_directory.iterdir()):
            raise EmptyInputDirectoryError(f"{input_directory} is empty!")
        return input_directory.resolve()

    @field_validator("output_files_directory", mode="before")
    def check_output_files_directory(cls, output_directory: Path):
        """Validate then resolve the output files directory."""
        if not output_directory.is_dir():
            raise ValueError(f"{output_directory} is not a valid output directory!")
        return output_directory.resolve()

    @field_validator("configuration_files_directory", mode="before")
    def check_config_files_directory(cls, configuration_files_directory: Path):
        """Validate then resolve the config files directory."""
        if not configuration_files_directory.is_dir():
            raise ValueError(f"{configuration_files_directory} is not a valid configuration directory!")
        return configuration_files_directory.resolve()


class Decoder:
    """Decoder Bindings."""

    def __init__(self, input_files_directory: str, output_files_directory: str, configurations_directory: str):
        """Initialise the bindings instance."""
        self.config = DecoderConfiguration(
            input_files_directory=Path(input_files_directory),
            output_files_directory=Path(output_files_directory),
            configuration_files_directory=Path(configurations_directory),
        )

    def decode(self, wmonum: str) -> None:
        """Run the Coriolis Decoder."""

        cmd = [
            "/app/run_decode_argo_2_nc_rt.sh",
            "rsynclog",
            "all",
            "configfile",
            "/mnt/data/config/decoder_conf.json",
            "xmlreport",
            "logfilexml.xml",
            "floatwmo",
            wmonum,
            "PROCESS_REMAINING_BUFFERS",
            "1",
        ]
        print("Running command:", cmd)
        try:
            result = subprocess.run(cmd, env=os.environ.copy(), check=True)
        except subprocess.CalledProcessError as e:
            print("Command failed with return code:", e.returncode)
            print("STDERR:", e.stderr)
        except FileNotFoundError:
            print("Invalid command")
        else:
            print("Decoding ran:", result)


if __name__ == "__main__":  # pragma: no cover
    # wmo = sys.argv
    # if len(sys.argv) < 2:
    #     raise ExecutionError("Usage: main.py <WMONUM>")
    # These are hardcoded for now, but will likely be passed by the calling code.
    decoder = Decoder("/mnt/data/rsync", "/mnt/data/output", "/mnt/data/config")
    decoder.decode("6902892")
    while True:
        pass

# Example command
# ./run_decode_argo_2_nc_rt.sh rsynclog all configfile /mnt/data/config/decoder_conf.json. xmlreport float.xml floatwmo 6902892 PROCESS_REMAINING_BUFFERS 1


