"""Decoder Bindings."""

import os
import re
import time
import subprocess
from pathlib import Path

from decoder_bindings.settings import Settings
from decoder_bindings.mock_data import info_dict, meta_dict, conf_dict  # Used for testing purposes only.
from decoder_bindings.utilities.dict2json import save_info_meta_conf

from pydantic import BaseModel, Field, field_validator


class EmptyInputDirectoryError(Exception):
    """Raised when the input directory is empty."""


class ExecutionError(Exception):
    """Raised when no wmonum is passed."""


class WmoValidationError(ValueError):
    """Raised when WMO number is invalid."""


class DecoderConfiguration(BaseModel):
    """Configuration used to pass to the decoder, with validation applied."""

    # Dossiers optionnels
    input_files_directory: Path | None = Field(default=None)
    output_files_directory: Path | None = Field(default=None)

    # Fichier de conf OBLIGATOIRE
    decoder_conf_file: Path

    # Chemin exécutable (bash wrapper)
    decoder_executable: Path | None = Field(default=None)
    # Chemin runtime MATLAB
    matlab_runtime: Path | None = Field(default=None)

    # Options d’exécution
    timeout_seconds: int | None = Field(default=3600, ge=1)  # 1h par défaut
    check_wmo_format: bool = True

    @field_validator("input_files_directory", mode="before")
    @classmethod
    def _validate_in_dir(cls, input_directory: Path | str | None):
        if input_directory is None:
            return None
        p = Path(input_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid input directory!")
        # On considère vide = erreur (comportement actuel)
        if not any(p.iterdir()):
            raise EmptyInputDirectoryError(f"{p} is empty!")
        return p.resolve()

    @field_validator("output_files_directory", mode="before")
    @classmethod
    def _validate_out_dir(cls, output_directory: Path | str | None):
        if output_directory is None:
            return None
        p = Path(output_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid output directory!")
        return p.resolve()

    @field_validator("decoder_conf_file", mode="before")
    @classmethod
    def _validate_conf(cls, conf_file: Path | str):
        p = Path(conf_file)
        if not p.is_file():
            raise ValueError(f"{p} is not a regular file!")
        return p.resolve()

    @field_validator("decoder_executable", mode="before")
    @classmethod
    def _validate_exec(cls, exec_file: Path | str):
        p = Path(exec_file)
        if not p.exists():
            raise ValueError(f"Decoder executable not found: {p}")
        if not os.access(p, os.X_OK):
            raise ValueError(f"Decoder executable not executable: {p}")
        return p.resolve()

    @field_validator("matlab_runtime", mode="before")
    @classmethod
    def _validate_runtime_dir(cls, runtime_directory: Path | str | None):
        if runtime_directory is None:
            return None
        p = Path(runtime_directory)
        if not p.is_dir():
            raise ValueError(f"{p} is not a valid output directory!")
        return p.resolve()


class Decoder:
    """Python bindings around the bash launcher for the MATLAB decoder."""

    _WMO_RE = re.compile(r"^\d{7}$")  # ex: '6902892'

    def __init__(
        self,
        decoder_conf_file: str | Path,
        decoder_executable: str | Path = None,
        matlab_runtime: str | Path = None,
        input_files_directory: str | Path | None = Field(default=None),
        output_files_directory: str | Path | None = Field(default=None),
        timeout_seconds: int | None = 3600,
        hold_after_run: int | None = None,
    ):
        """Initialise the bindings instance."""
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
        if not isinstance(wmonum, str):
            raise WmoValidationError("WMOnum must be a string.")
        if not Decoder._WMO_RE.match(wmonum):
            raise WmoValidationError(
                f"Invalid WMO '{wmonum}'. Expected 7 digits (e.g., '6902892')."
            )

    def _build_cmd(self, wmonum: str) -> list[str]:
        cmd: list[str] = [
            str(self.config.decoder_executable),
            str(self.config.matlab_runtime),
            "rsynclog",
            "all",
            "configfile",
            str(self.config.decoder_conf_file),
            "xmlreport",
            "logfilexml.xml",
            "floatwmo",
            wmonum,
            "PROCESS_REMAINING_BUFFERS",
            "1",
        ]

        # Si l’utilisateur veut imposer les chemins I/O, on ne les ajoute que s’ils sont tous deux fournis
        if self.config.input_files_directory is not None:
            if self.config.output_files_directory is None:
                raise ValueError(
                    "If 'input_files_directory' is provided, 'output_files_directory' must also be provided."
                )
            cmd.extend(
                [
                    "DIR_INPUT_RSYNC_DATA",
                    str(self.config.input_files_directory),
                    "DIR_OUTPUT_NETCDF_FILE",
                    str(self.config.output_files_directory),
                ]
            )
        return cmd

    def _post_run_hold(self) -> None:
        """Remplace la boucle infinie par un hold optionnel et contrôlable."""
        if self.hold_after_run is None or self.hold_after_run == 0:
            return
        if self.hold_after_run > 0:
            time.sleep(self.hold_after_run)
            return
        # hold “infini” mais en dormant (pas de burn CPU)
        while True:
            time.sleep(60)

    def decode(
        self,
        wmonum: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run the Coriolis Decoder."""
        if self.config.check_wmo_format:
            self._validate_wmo(wmonum)

        cmd = self._build_cmd(wmonum)
        try:
            print(cmd)
            result = subprocess.run(
                cmd,
                env=os.environ.copy(),
                check=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.CalledProcessError as e:
            print("Command failed with return code:", e.returncode)
            print("STDERR:", e.stderr)
        except FileNotFoundError:
            print("Invalid command")
        else:
            print("Decoding ran:", result)

        # << remplace `while True: pass`
        self._post_run_hold()


if __name__ == "__main__":  # pragma: no cover
    print("Running...")
    # read settings
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

    # These are hardcoded for now, but will likely be passed by the calling code.
    decoder = Decoder(
        decoder_executable=str(settings.DECODER_EXECUTABLE),
        matlab_runtime=str(settings.MATLAB_RUNTIME),
        decoder_conf_file=str(config_dir / "decoder_conf.json"),
        input_files_directory=str(settings.DECODER_INPUT_DIR),
        output_files_directory=str(output_dir),
        timeout_seconds=settings.DECODER_TIMEOUT,  # ← configurable
    )
    decoder.decode("6902892")
