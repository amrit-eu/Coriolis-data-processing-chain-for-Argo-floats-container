from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
