"""Decoder Bindings."""

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, field_validator


class EmptyInputDirectoryError(Exception):
    """Raised when the input directory is empty."""


class ExecutionError(Exception):
    """Raised when no wmonum is passed."""


class DecoderConfiguration(BaseModel):
    """Configuration used to pass to the decoder, with validation applied."""

    input_files_directory: Path | None
    output_files_directory: Path | None
    decoder_conf_file: Path


    @field_validator("input_files_directory", mode="before")
    def check_input_files_directory(cls, input_directory: Path):
        """Validate then resolve the input files directory if not None."""
        if input_directory is None:
            return input_directory
        if not input_directory.is_dir():
            raise ValueError(f"{input_directory} is not a valid input directory!")

        if not any(input_directory.iterdir()):
            raise EmptyInputDirectoryError(f"{input_directory} is empty!")
        return input_directory.resolve()

    @field_validator("output_files_directory", mode="before")
    def check_output_files_directory(cls, output_directory: Path):
        """Validate then resolve the output files directory if not None."""
        if output_directory is None:
            return output_directory
        if not output_directory.is_dir():
            raise ValueError(f"{output_directory} is not a valid output directory!")
        return output_directory.resolve()


class Decoder:
    """Decoder Bindings."""

    def __init__(self, input_files_directory: str | None, output_files_directory: str | None, decoder_conf_file: str):
        """Initialise the bindings instance."""
        self.config = DecoderConfiguration(
            input_files_directory=Path(input_files_directory) if isinstance(input_files_directory, str) else None,
            output_files_directory=Path(output_files_directory) if isinstance(output_files_directory, str) else None,
            decoder_conf_file=Path(decoder_conf_file),
        )

    def decode(self, wmonum: str, rsync_file: str) -> None:
        """Run the Coriolis Decoder."""
        cmd = [
            "/app/run_decode_argo_2_nc_rt.sh",
            "rsynclog",
            rsync_file,
            "configfile",
            str(self.config.decoder_conf_file),
            "xmlreport",
            "logfilexml.xml",
            "floatwmo",
            wmonum,
            "PROCESS_REMAINING_BUFFERS",
            "1",
        ]
        # If passed, extend the command to include the new input/output arguments to the decoder.
        if self.config.input_files_directory is not None:
            cmd.extend(
                [
                    "DIR_INPUT_RSYNC_DATA",
                    str(self.config.input_files_directory),
                    "DIR_OUTPUT_NETCDF_FILE",
                    str(self.config.output_files_directory),
                ]
            )

        # Regarding the 'except' clauses, these will return various non 200 status codes when integrated into the API.
        try:
            result = subprocess.run(cmd, env=os.environ.copy(), check=True)
        except subprocess.CalledProcessError as e:
            print("Command failed with return code:", e.returncode)
            print("STDERR:", e.stderr)
        except FileNotFoundError:
            print("Invalid command")
        else:
            print("Decoding ran:", result)


