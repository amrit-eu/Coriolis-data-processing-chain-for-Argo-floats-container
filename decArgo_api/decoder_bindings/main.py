"""API Entrypoint."""

import logging
from pathlib import Path
import json
import shutil
import tempfile
import time

from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import StreamingResponse

from decoder_bindings.decoder import Decoder, DecoderError
from decoder_bindings.file_manager import FileManager, FileManagerError
from decoder_bindings.zip_nc_files import ZipNCFiles, ZipNCFilesError

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.post("/decode_float/{wmonum}")
async def decode_float(wmonum: str, files: list[UploadFile], float_metadata: str = Form(...)):
    """Invoke the decoder and return a ZIP file of the decoded NC files.

    Args:
        wmonum: The WMONUM of the raw files to be decoded.
        files: A list of files to be decoded.

    Returns: A zipfile, or a dict containing an error message.
    """
    logging.info("Running for WMONUM: %s", wmonum)
    logging.info("Running for Files: %s", files)


    ### Move to new module!
    dicts =  json.loads(float_metadata)
    float_info = dicts.get("float_info")
    meta_info = dicts.get("float_meta_info")
    imei = float_info.get("PTT")

    with open(f"/mnt/data/config/json_float_info/{wmonum}_{imei}_info.json", mode="w") as json_float_info: 
        json.dump(float_info, json_float_info, indent=4)


    with open(f"/mnt/data/config/json_float_meta/{wmonum}_meta.json", mode="w") as json_float_meta: 
        json.dump(meta_info, json_float_meta, indent=4)

    ################################

    try:
        rsync_file_name = FileManager(files).run()

        with tempfile.TemporaryDirectory(dir="/mnt/data") as temporary_output_directory:
            decoder = Decoder(
                input_files_directory=None,
                output_files_directory=temporary_output_directory,
                decoder_conf_file="/mnt/data/config/decoder_conf.json",
            )
            decoder.decode(wmonum=wmonum, rsync_file=rsync_file_name)
            zipfile, zip_filename = ZipNCFiles(wmonum=wmonum).zip_all_nc_files()

            iridium_path = f"/mnt/data/output/iridium/{imei}_{wmonum}"
            nc_path = f"/mnt/data/output/nc/{wmonum}"
            if Path(iridium_path).is_dir():
                shutil.rmtree(iridium_path)

            if Path(nc_path).is_dir():
                shutil.rmtree(nc_path)
            
    except (FileManagerError, ZipNCFilesError, DecoderError):
        return {"Message": "Zip file not generated. Check the logs for more information."}
    else:
        return StreamingResponse(
            zipfile, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )

