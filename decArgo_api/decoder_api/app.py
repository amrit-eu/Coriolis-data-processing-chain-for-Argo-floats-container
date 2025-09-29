import os
from pathlib import Path
from uuid import uuid4

from decoder_bindings import save_info_meta_conf, Decoder
from decoder_bindings.settings import Settings
from fastapi import FastAPI

ROOT_PATH = os.getenv("API_ROOT_PATH", "")

app = FastAPI(root_path=ROOT_PATH)


@app.get("/")
def app_status():
    """
    Health check endpoint to confirm that the app is running.
    :return: status message
    """
    return {"status": "OK"}


@app.post("/decode-files")
def check_file_list(
    wmonum: str, conf_dict: dict, info_dict: dict = None, meta_dict: dict = None
):
    """
    Main endpoint to decode files.
    :param files:
        WMO of float to decode
    :param conf_dict:
        Decoding configuration
    :return:
        { "results": ValidationResult object }
    """
    settings = Settings()

    request_id = uuid4()
    request_output_file_dir = Path(f"{settings.DECODER_OUTPUT_DIR}/{request_id}")
    os.makedirs(request_output_file_dir)

    try:
        float_info = save_info_meta_conf(
            config_dir=f"{request_output_file_dir}/config",
            float_info_dir=f"{request_output_file_dir}/config/decArgo_config_floats2/json_float_info",
            float_meta_dir=f"{request_output_file_dir}/config/decArgo_config_floats2/json_float_meta",
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
        decoder_executable=settings.DECODER_EXECUTABLE,
        matlab_runtime=settings.MATLAB_RUNTIME,
        decoder_conf_file=f"{request_output_file_dir}/config/decoder_conf.json",
        input_files_directory=settings.DECODER_INPUT_DIR,
        output_files_directory=f"{request_output_file_dir}/output",
        timeout_seconds=3600,
    )
    decoder.decode(wmonum)

    # return results
