"""Decoder service settings.

This module defines the configuration model for the decoder, based on
`pydantic-settings.BaseSettings`. It centralizes filesystem paths and runtime
options, and allows overriding via environment variables when running inside
Docker or other environments.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration for the decoder service.

    Attributes:
    -----------
    DECODER_OUTPUT_DIR:
        Path where decoder outputs will be written.
    DECODER_CONFIG_DIR:
        Path to the configuration files used by the decoder.
    DECODER_INPUT_DIR:
        Path to the input files for the decoder.
    DECODER_EXECUTABLE:
        Path to the bash wrapper that launches the MATLAB-based decoder.
    MATLAB_RUNTIME:
        Path to the MATLAB Runtime root directory.
    DECODER_TIMEOUT:
        Maximum time (in seconds) before a decoder run is terminated.

    Doc
    -----
    - All fields can be overridden by environment variables.
    - `.env` files are ignored by default (docker-friendly).
    """

    DECODER_OUTPUT_DIR: Path = Field(default=Path("../decArgo_demo/output"))
    DECODER_CONFIG_DIR: Path = Field(default=Path("../decArgo_demo/config"))
    DECODER_INPUT_DIR: Path = Field(default=Path("../decArgo_demo/input"))
    DECODER_EXECUTABLE: Path = Field(default=Path("../decArgo_soft/exec/run_decode_argo_2_nc_rt.sh"))
    MATLAB_RUNTIME: Path = Field(default=Path("/home/lbruvryl/development/tmp/tmp_tc/matlab_runtime/R2022b"))
    DECODER_TIMEOUT: int = 3600

    model_config = SettingsConfigDict(
        env_file=None,  # do not load .env automatically (docker friendly)
        case_sensitive=False,
        extra="ignore",
    )
