"""
Decoder Bindings
================

Python bindings around the MATLAB-based Coriolis decoder, launched through a bash
wrapper. This module provides:

- A Pydantic configuration model with validation to ensure the filesystem setup
  is correct before decoding starts.
- A `Decoder` class that builds the CLI command and invokes the external
  decoder process, with optional output capture.
- A small `__main__` harness to exercise the binding with mock data.

This file intentionally preserves *all* existing functional behavior.
Only documentation (docstrings and comments) has been added.
"""

import os
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime

from decoder_bindings.settings import Settings
from decoder_bindings.mock_data import (
    info_dict,
    meta_dict,
    conf_dict,
)  # Used for testing purposes only.
from decoder_bindings.utilities.dict2json import save_info_meta_conf

from pydantic import BaseModel, Field, field_validator


# -----------------------------------------------------------------------------
# Custom exceptions
# -----------------------------------------------------------------------------

class EmptyInputDirectoryError(Exception):
    """Raised when the configured input directory exists but is empty."""


class ExecutionError(Exception):
    """Raised when decode is attempted with missing required inputs (e.g., WMO)."""


class WmoValidationError(ValueError):
    """Raised when a WMO number does not match the expected 7-digit format."""


# -----------------------------------------------------------------------------
# Configuration model
# -----------------------------------------------------------------------------

class DecoderConfiguration(BaseModel):
    """
    Configuration passed to the decoder, with validation applied.

    Fields
    ------
    input_files_directory:
        Optional path to the input directory (must exist and not be empty if provided).
    output_files_directory:
        Optional path where decoder outputs will be written (must exist).
    decoder_conf_file:
        **Required** path to the decoder JSON configuration file (must exist).
    decoder_executable:
        Optional path to the decoder bash wrapper executable (must exist and be executable).
    matlab_runtime:
        Optional path to the MATLAB Runtime root directory (must exist).
    timeout_seconds:
        Optional timeout (in seconds) for the external process. Default is 3600 (1 hour).
    check_wmo_format:
        Whether to validate that WMO numbers match the expected pattern. Default: True.

    Validation behavior
    -------------------
    - If `input_files_directory` is set: it must be a directory, and **not empty**.
    - If `output_files_directory` is set: it must be a directory.
    - `decoder_conf_file` must be an existing regular file.
    - `decoder_executable` must exist and be executable (`+x`).
    - `matlab_runtime` must be an existing directory.

    All paths are resolved to absolute paths via `Path.resolve()` when valid.
    """

    # Optional directories
    input_files_directory: Path | None = None
    output_files_directory: Path | None = None

    # Required decoder config file (JSON)
    decoder_conf_file: Path

    # Executable (bash wrapper) and MATLAB runtime
    decoder_executable: Path | None = Field(default=None)
    matlab_runtime: Path | None = Field(default=None)

    # Runtime options
    timeout_seconds: int | None = Field(default=3600, ge=1)  # Default: 1 hour
    check_wmo_format: bool = True

    @field_validator("input_files_directory", mode="before")
    @classmethod
    def _validate_in_dir(cls, input_directory: Path | str | None):
        """
        Ensure the input directory exists and is not empty (if provided).

        Raises
        ------
        ValueError
            If the path is not an existing directory.
        EmptyInputDirectoryError
            If the directory is empty.
        """
        if input_directory is None:
            return None
        p = Path(input_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid input directory!")
        # Current behavior: empty input directory is considered an error.
        if not any(p.iterdir()):
            raise EmptyInputDirectoryError(f"{p} is empty!")
        return p.resolve()

    @field_validator("output_files_directory", mode="before")
    @classmethod
    def _validate_out_dir(cls, output_directory: Path | str | None):
        """
        Ensure the output directory exists (if provided).

        Raises
        ------
        ValueError
            If the path is not an existing directory.
        """
        if output_directory is None:
            return None
        p = Path(output_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid output directory!")
        return p.resolve()

    @field_validator("decoder_conf_file", mode="before")
    @classmethod
    def _validate_conf(cls, conf_file: Path | str):
        """
        Ensure the decoder configuration file exists as a regular file.

        Raises
        ------
        ValueError
            If the file does not exist or is not a regular file.
        """
        p = Path(conf_file)
        if not p.is_file():
            raise ValueError(f"{p} is not a regular file!")
        return p.resolve()

    @field_validator("decoder_executable", mode="before")
    @classmethod
    def _validate_exec(cls, exec_file: Path | str):
        """
        Ensure the decoder executable exists and is executable.

        Raises
        ------
        ValueError
            If the executable is missing or lacks execute permissions.
        """
        p = Path(exec_file)
        if not p.exists():
            raise ValueError(f"Decoder executable not found: {p}")
        if not os.access(p, os.X_OK):
            raise ValueError(f"Decoder executable not executable: {p}")
        return p.resolve()

    @field_validator("matlab_runtime", mode="before")
    @classmethod
    def _validate_runtime_dir(cls, runtime_directory: Path | str | None):
        """
        Ensure the MATLAB runtime directory exists (if provided).

        Raises
        ------
        ValueError
            If the path is not an existing directory.
        """
        if runtime_directory is None:
            return None
        p = Path(runtime_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid output directory!")
        return p.resolve()


# -----------------------------------------------------------------------------
# Decoder wrapper
# -----------------------------------------------------------------------------

class Decoder:
    """
    Python bindings around the bash launcher for the MATLAB decoder.

    Responsibilities
    ----------------
    - Validate the WMO number (if enabled).
    - Build the command-line arguments for the external decoder based on the
      configuration and the requested WMO.
    - Ensure output subdirectories exist if an output directory is configured.
    - Run the external process via `subprocess.run`, optionally capturing stdout/stderr.
    - Optionally "hold" after the run (sleep), replacing a previous infinite loop.

    Notes
    -----
    - This class *does not* modify files under the input directory.
    - It will create subdirectories under the configured `output_files_directory`
      as needed for the decoder (`iridium`, `log`, `csv`, `xml`, `nc`).
    """

    _WMO_RE = re.compile(r"^\d{7}$")  # e.g., '6902892'

    def __init__(
        self,
        decoder_conf_file: str | Path,
        decoder_executable: str | Path = None,
        matlab_runtime: str | Path = None,
        input_files_directory: str | Path | None = None,
        output_files_directory: str | Path | None = None,
        timeout_seconds: int | None = 3600,
        hold_after_run: int | None = None,
    ):
        """
        Initialize a `Decoder` instance.

        Parameters
        ----------
        decoder_conf_file:
            Path to the decoder JSON config file (must exist).
        decoder_executable:
            Path to the decoder bash wrapper (must exist and be executable).
        matlab_runtime:
            Path to the MATLAB Runtime root directory (must exist).
        input_files_directory:
            Optional input directory (must exist and not be empty if provided).
        output_files_directory:
            Optional output directory (must exist if provided). Subfolders used by the
            decoder are created on demand if this is set.
        timeout_seconds:
            Optional subprocess timeout in seconds. Default is 3600 (1 hour).
        hold_after_run:
            Optional post-run hold time in seconds. If positive, the call will sleep for
            that many seconds; if 0 or None, it returns immediately; if negative,
            it sleeps in a loop indefinitely.

        Raises
        ------
        ValueError
            If any validated path is missing or invalid.
        EmptyInputDirectoryError
            If the input directory is provided but empty.
        """
        self.config = DecoderConfiguration(
            input_files_directory=input_files_directory,
            output_files_directory=output_files_directory,
            decoder_conf_file=decoder_conf_file,
            decoder_executable=decoder_executable,
            matlab_runtime=matlab_runtime,
            timeout_seconds=timeout_seconds,
        )
        self.hold_after_run = hold_after_run

    @staticmethod
    def _validate_wmo(wmonum: str):
        """
        Validate that the WMO number is a 7-digit string.

        Parameters
        ----------
        wmonum:
            The WMO identifier to validate.

        Raises
        ------
        WmoValidationError
            If `wmonum` is not a `str` or does not match the expected pattern.
        """
        if not isinstance(wmonum, str):
            raise WmoValidationError("WMOnum must be a string.")
        if not Decoder._WMO_RE.match(wmonum):
            raise WmoValidationError(
                f"Invalid WMO '{wmonum}'. Expected 7 digits (e.g., '6902892')."
            )

    def _build_cmd(self, wmonum: str) -> list[str]:
        """
        Build the command-line argument list to run the decoder process.

        The command includes:
        - Executable path and MATLAB runtime
        - Logging and config switches
        - The requested WMO
        - Output directory bindings (if configured)

        Parameters
        ----------
        wmonum:
            The WMO identifier to pass to the decoder.

        Returns
        -------
        list[str]
            The full command argument vector.

        Side Effects
        ------------
        If `output_files_directory` is set, this method ensures that the decoder’s
        required subdirectories exist: `iridium`, `log`, `csv`, `xml`, `nc`.
        """
        file_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        cmd: list[str] = [
            str(self.config.decoder_executable),
            str(self.config.matlab_runtime),
            "rsynclog",
            "all",
            "configfile",
            str(self.config.decoder_conf_file),
            "xmlreport",
            f"xmlreport_{wmonum}_{file_date}.xml",
            "floatwmo",
            wmonum,
            "PROCESS_REMAINING_BUFFERS",
            "1",
        ]

        # NOTE: Input-directory bindings are intentionally commented out for now.
        # If you enable this section later, consider mapping exact expected subpaths
        # and surfacing them in the config schema.
        #
        # if self.config.input_files_directory is not None:
        #     cmd.extend(
        #         [
        #             "DIR_INPUT_RSYNC_DATA",
        #             f"{self.config.input_files_directory}/archive/cycle",
        #             "DIR_INPUT_RSYNC_LOG",
        #             f"{self.config.input_files_directory}/rsync_list/",
        #         ]
        #     )

        if self.config.output_files_directory is not None:
            iridium_data_dir = self.config.output_files_directory / "iridium"
            log_dir = self.config.output_files_directory / "log"
            csv_dir = self.config.output_files_directory / "csv"
            xml_dir = self.config.output_files_directory / "xml"
            data_dir = self.config.output_files_directory / "nc"

            # Append decoder output destinations
            cmd.extend(
                [
                    "IRIDIUM_DATA_DIRECTORY",
                    str(iridium_data_dir),
                    "DIR_OUTPUT_LOG_FILE",
                    str(log_dir),
                    "DIR_OUTPUT_CSV_FILE",
                    str(csv_dir),
                    "DIR_OUTPUT_XML_FILE",
                    str(xml_dir),
                    "DIR_OUTPUT_NETCDF_FILE",
                    str(data_dir),
                    "DIR_OUTPUT_NETCDF_TRAJ_3_2_FILE",
                    str(data_dir),
                ]
            )

            # Ensure filesystem layout exists before launching
            iridium_data_dir.mkdir(parents=True, exist_ok=True)
            log_dir.mkdir(parents=True, exist_ok=True)
            csv_dir.mkdir(parents=True, exist_ok=True)
            xml_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

        return cmd

    def _post_run_hold(self) -> None:
        """
        Optional post-run hold to replace a previous infinite loop.

        Behavior
        --------
        - If `hold_after_run` is None or 0: return immediately.
        - If `hold_after_run` > 0: sleep for that many seconds, then return.
        - If `hold_after_run` < 0: sleep indefinitely in 60-second intervals.

        Notes
        -----
        This method intentionally sleeps (does not busy-wait) to avoid CPU burn.
        """
        if self.hold_after_run is None or self.hold_after_run == 0:
            return
        if self.hold_after_run > 0:
            time.sleep(self.hold_after_run)
            return
        # Infinite hold: passive sleep loop
        while True:
            time.sleep(60)

    def decode(
        self,
        wmonum: str,
        capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        """
        Run the Coriolis decoder for the given WMO.

        Parameters
        ----------
        wmonum:
            WMO identifier to decode. Validated if `check_wmo_format` is True.
        capture_output:
            If True, capture stdout/stderr and store them in the returned object.

        Returns
        -------
        subprocess.CompletedProcess[str]
            **Note:** Although the type annotation says `CompletedProcess[str]`, the
            current implementation returns `result.stdout` (a `str`) at the end of
            the method. This docstring reflects the code as-is, without altering
            behavior.

        Raises
        ------
        WmoValidationError
            If `wmonum` fails validation and `check_wmo_format` is enabled.
        subprocess.CalledProcessError
            If the external process exits with a non-zero code *and* you re-raise.
            (Currently the code prints error details but does not re-raise.)
        FileNotFoundError
            If the configured executable is not found.
        """
        if self.config.check_wmo_format:
            self._validate_wmo(wmonum)

        cmd = self._build_cmd(wmonum)
        try:
            result = subprocess.run(
                cmd,
                env=os.environ.copy(),
                check=True,
                text=True,
                timeout=self.config.timeout_seconds,
                capture_output=capture_output,
            )
        except subprocess.CalledProcessError as e:
            # Current behavior: print details; no re-raise.
            print("Command failed with return code:", e.returncode)
            print("STDERR:", e.stderr)
        except FileNotFoundError:
            # Current behavior: print; no re-raise.
            print("Invalid command")
        else:
            # Successful run
            print("Decoding ran:", result)

        # Replace previous infinite loop with controlled hold (if configured)
        self._post_run_hold()

        # Current behavior: return stdout (string), not the CompletedProcess object.
        return result.stdout


# -----------------------------------------------------------------------------
# Local harness (__main__)
# -----------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    """
    Minimal local harness to exercise the bindings with mock data.

    This section:
    - Loads settings (from env/defaults).
    - Prepares a `config` and `output` directory under `DECODER_OUTPUT_DIR`.
    - Writes mock info/meta/conf JSON files as the decoder expects.
    - Instantiates a `Decoder` and runs it for WMO '6902892'.

    Intended for quick local smoke tests, not for production usage.
    """
    print("Running...")
    settings = Settings()

    request_root: Path = Path(settings.DECODER_OUTPUT_DIR)
    config_dir = request_root / "config"
    output_dir = request_root / "files"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        float_info = save_info_meta_conf(
            config_dir=str(config_dir),
            float_info_dir=str(config_dir / "decArgo_config_floats2/json_float_info"),
            float_meta_dir=str(config_dir / "decArgo_config_floats2/json_float_meta"),
            info=info_dict,
            meta=meta_dict,
            decoder_conf=conf_dict,
        )
        for key, value in float_info.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error saving float info : {e}")

    decoder = Decoder(
        decoder_executable=str(settings.DECODER_EXECUTABLE),
        matlab_runtime=str(settings.MATLAB_RUNTIME),
        decoder_conf_file=str(config_dir / "decoder_conf.json"),
        input_files_directory=str(settings.DECODER_INPUT_DIR),
        output_files_directory=str(output_dir),
        timeout_seconds=settings.DECODER_TIMEOUT,  # ← configurable
    )
    decoder.decode("6902892")
