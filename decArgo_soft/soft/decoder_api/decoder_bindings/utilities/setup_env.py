import os
from datetime import datetime

def write_env_file(wmonum:str, directories:dict, decoder_command:str,  env_path: str = ".env"):
    """
    Write the given environment variables to a .env file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    decoder_command = (
            f"/mnt/runtime rsynclog all "
            f"configfile /mnt/data/config/decoder_conf.json "
            f"xmlreport co041404_{timestamp}_{wmonum}.xml "
            f"floatwmo {wmonum} PROCESS_REMAINING_BUFFERS 1"
        )
    env = {
            "FLOAT_WMO": str(wmonum),
            "DECODER_COMMAND": str(decoder_command),
            "DECODER_DATA_INPUT_VOLUME": str(directories["input"]),
            "DECODER_DATA_CONF_VOLUME": str(directories["config"]),
            "DECODER_DATA_OUTPUT_VOLUME": str(directories["output"]),
            "RUNTIME_IMAGE": "ghcr.io/euroargodev/coriolis-data-processing-chain-for-argo-floats/runtime/matlab",
            "RUNTIME_IMAGE_TAG": "R2022b",
            "DECODER_IMAGE": "ghcr.io/euroargodev/coriolis-data-processing-chain-for-argo-floats-container",
            "DECODER_IMAGE_TAG": "066a.1",
            "DECODER_RUNTIME_VOLUME": "runtime-matlab-volume",
            "USER_ID": str(os.getuid()),
            "GROUP_ID": str(os.getgid()),
        }
    lines = []
    for k, v in env.items():
        lines.append(f"{k}={v}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
