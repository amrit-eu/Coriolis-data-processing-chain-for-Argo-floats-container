import os
from pathlib import Path
from uuid import uuid4

from decoder_bindings import save_info_meta_conf, Decoder
from argofilechecker_python_wrapper import FileChecker
from fastapi import FastAPI, UploadFile

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
def check_file_list(wmonum: str, conf_dict: dict, info_dict: dict = None, meta_dict: dict = None):
    """
    Main endpoint to decode files.
    :param files:
        WMO of float to decode
    :param conf_dict:
        Decoding configuration
    :return:
        { "results": ValidationResult object }
    """

    request_id = uuid4()
    request_file_dir = Path(f"/home/app/input/{request_id}")
    os.makedirs(request_file_dir)

    try:
        float_info = save_info_meta_conf(
            config_dir="./tmp/config",
            float_info_dir="./tmp/config/decArgo_config_floats2/json_float_info",
            float_meta_dir="./tmp/config/decArgo_config_floats2/json_float_meta",
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
        decoder_executable="../decArgo_soft/exec/run_decode_argo_2_nc_rt.sh",
        matlab_runtime="/home/lbruvryl/development/tmp/tmp_tc/matlab_runtime/R2022b",
        decoder_conf_file="../decArgo_demo/config/decoder_conf.json",
        input_files_directory="../decArgo_demo/input",
        output_files_directory="../decArgo_demo/output",
        timeout_seconds=3600,
    )
    decoder.decode(wmonum)

    # return results
