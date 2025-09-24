"""Decoder Bindings."""

import sys
from pathlib import Path
import os

from typing import Optional, Dict, Any
import re
from datetime import datetime

import subprocess
from pydantic import BaseModel, field_validator, computed_field
from utilities.setup_env import write_env_file
from utilities.dict2json import save_info_meta_conf
from utilities.setup_dir import ( 
     setup_decoder_directories_for_float,
     get_volume_paths_for_float,
     cleanup_old_float_directories,
     list_existing_float_directories,
     copy_rsync_list_files
)
from mock_data import float1_info as info_dict, float1_meta as meta_dict, float1_conf as decoder_conf

class EmptyInputDirectoryError(Exception):
    """Raised when the input directory is empty."""


class ExecutionError(Exception):
    """Raised when no wmonum is passed."""

class FloatInfo(BaseModel):
    """Float information model with validation for WMO and PTT extraction."""
    
    WMO: str
    PTT: str

    # Allow additional fields that might be in the info dict
    model_config = {"extra": "allow"}
    
    @field_validator("WMO", mode="before")
    def validate_wmo(cls, wmo):
        """extract the WMO."""
        return str(wmo).strip()

    
    @field_validator("PTT", mode="before") 
    def validate_ptt(cls, ptt):
        """Extract PTT."""
        return str(ptt).strip()
    
class FloatMetaInfo(BaseModel):
    """Float meta information model."""
    model_config = {"extra": "allow"}
    
    def __init__(self, **data):
        """Accept any fields in the metadata."""
        super().__init__(**data)

class DecoderConfiguration(BaseModel):
    """Configuration used to pass to the decoder, with validation applied."""

    float_info: FloatInfo
    meta_info: FloatMetaInfo
    input_files_directory: Path
    output_files_directory: Path
    configuration_files_directory: Path
    base_dir: Path = Path("./decArgo")

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

    @classmethod
    def from_dicts(cls, info_dict: Dict[str, Any], meta_dict: Optional[Dict[str, Any]] = None):
        """Create FloatConfiguration from dictionaries."""
        float_info = FloatInfo(**info_dict)
        meta_info = FloatMetaInfo(**meta_dict) if meta_dict else None
        
        return cls(
            float_info=float_info,
            meta_info=meta_info
        )

    
    @computed_field
    @property
    def wmo(self) -> str:
        """Get WMO from float info."""
        return self.float_info.WMO
    
    @computed_field 
    @property
    def ptt(self) -> str:
        """Get PTT from float info."""
        return self.float_info.PTT
     
class Decoder:
    """Decoder Bindings."""

    def __init__(self, input_files_directory: str, output_files_directory: str, configurations_directory: str, base_dir:str, info: dict = None, meta: dict = None	):
        """Initialise the bindings instance."""
        self.config = DecoderConfiguration(
            input_files_directory=Path(input_files_directory),
            output_files_directory=Path(output_files_directory),
            configuration_files_directory=Path(configurations_directory),
            float_info=FloatInfo(**info) if info else None,
            meta_info=FloatMetaInfo(**meta) if meta else None,
            base_dir=Path(base_dir)
        )

    
    def list_processed_floats(self):
        """List all previously processed float directories."""
        return list_existing_float_directories(self.base_dir)
    
    def cleanup_old_runs(self):
        """Clean up old float processing runs."""
        cleanup_old_float_directories(self.config.base_dir, self.config.wmo)

    def run_decoder(self, wmonum: str, directories:dict) -> None:
        """Run the Coriolis Decoder."""
        if not wmonum:
            raise ValueError("FLOAT_WMO required!")
        # Build decoder command (matches shell script)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        decoder_command = (
            f"/mnt/runtime rsynclog all "
            f"configfile /mnt/data/config/decoder_conf.json "
            f"xmlreport co041404_{timestamp}_{wmonum}.xml "
            f"floatwmo {wmonum} PROCESS_REMAINING_BUFFERS 1"
        )
        write_env_file(wmonum, directories, decoder_command, ".env")

        # Point docker compose to your two files
        compose_files = [
            "-f", "compose.yaml",
            "-f", "compose.matlab-runtime.yaml"
        ]
       
        try:
            subprocess.run(["docker", "compose", *compose_files, "down"], check=True )
            result = subprocess.run(["docker", "compose", *compose_files, "up"], check=True)
        except subprocess.CalledProcessError as e:
            print("Command failed with return code:", e.returncode)
            print("STDERR:", e.stderr)
        except FileNotFoundError:
            print("Invalid command")
        else:
            print("Decoding ran:", result)


if __name__ == "__main__":  # pragma: no cover
    print("Running...")

    # These are commented out for now, but we'll want to raise an error if no WMONUM is passed.

    # wmo = sys.argv
    # if len(sys.argv) < 2:
    #     raise ExecutionError("Usage: main.py <WMONUM>")

    
    
    input_dir = "./decArgo_demo/input"
    output_dir = "./decArgo_demo/output"  
    config_dir = "./decArgo_demo/config"
    base_dir = "./decArgo_workspace"#replace this with ./tmp/decArgo_workspace for passing to decoder container


    decoder = Decoder(input_dir, output_dir, config_dir, base_dir, info_dict, meta_dict )
    config_directories = setup_decoder_directories_for_float(decoder.config.wmo, decoder.config.base_dir, timestamp=True)
    copy_rsync_list_files(f"{input_dir}/rsync_list", config_directories["rsync_list"])
    config_files = save_info_meta_conf(
        decoder.config.wmo,
        decoder.config.ptt,
        config_directories,
        decoder.config.float_info.model_dump(),
        decoder.config.meta_info.model_dump(),
        decoder_conf)
    print(f"Saved info to {config_files['info_file']} and meta to {config_files['meta_file']}")
   
    decoder.run_decoder("6902892", directories=config_directories)
    #decoder.cleanup_old_runs()

# Example command
# ./run_decode_argo_2_nc_rt.sh rsynclog all configfile /mnt/data/config/decoder_conf.json xmlreport float.xml floatwmo 6902892 PROCESS_REMAINING_BUFFERS 1


