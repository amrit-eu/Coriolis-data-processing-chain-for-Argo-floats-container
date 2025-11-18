"""Decoder Bindings."""

import logging
import os
import subprocess
import traceback
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class EmptyInputDirectoryError(FileNotFoundError):
    """Raised when the input directory is empty."""


class ExecutionError(ValueError):
    """Raised when no wmonum is passed to the decoder which is required to run the decode process."""


class DecoderError(RuntimeError):
    """Raised when an error is detected during the decoding stage."""


class DecoderConfiguration(BaseModel):
    """Configuration used to pass to the decoder, with validation applied."""

    input_files_directory: Path | None = Field(
        default=None, description="Directory containing the input files for the decoder."
    )
    output_files_directory: Path | None = Field(
        default=None, description="Directory where the decoded files will be written to"
    )
    decoder_conf_file: Path = Field(..., description="Path to the decoder configuration file.")

    @field_validator("input_files_directory", mode="before")
    def check_input_files_directory(cls, input_directory: Path):
        """Validate then resolve the input files directory if not None."""
        if input_directory is None:
            return input_directory
        if not input_directory.is_dir():
            raise NotADirectoryError(f"{input_directory} is not a valid input directory!")

        if not any(input_directory.iterdir()):
            raise EmptyInputDirectoryError(f"{input_directory} is empty!")
        return input_directory.resolve()

    @field_validator("output_files_directory", mode="before")
    def check_output_files_directory(cls, output_directory: Path):
        """Validate then resolve the output files directory if not None."""
        if output_directory is None:
            return output_directory
        if not output_directory.is_dir():
            raise NotADirectoryError(f"{output_directory} is not a valid output directory!")
        return output_directory.resolve()


class Decoder:
    """Code to bind to the Coriolis Decoder and provide an entrypoint via an API."""

    def __init__(
        self,
        decoder_conf_file: str,
        input_files_directory: str | None = None,
        output_files_directory: str | None = None,
    ):
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
        # If passed, extend the command to include the new input/out arguments to the decoder.
        if self.config.output_files_directory is not None:
            cmd.extend(
                [
                    "DIR_OUTPUT_NETCDF_FILE",
                    str(self.config.output_files_directory),
                ]
            )
        if self.config.input_files_directory is not None:
            cmd.extend(
                [
                    "DIR_INPUT_RSYNC_DATA",
                    str(self.config.input_files_directory),
                ]
            )
        try:
            logging.info("Starting decode process.")
            result = subprocess.run(cmd, env=os.environ.copy(), check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logging.error("An error occurred during the decoder process: %s", traceback.format_exc())
            raise DecoderError from exc
        else:
            # Check the decoder output for any issues.
            if "ERROR:" in result.stdout:
                logging.error("An error occurred during the decoder process: %s", result.stdout)
                raise DecoderError(result.stdout)

        logging.info("Decoding finished succesfully.")
        return True
