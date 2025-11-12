"""API Entrypoint."""

import os
import shutil
from pathlib import Path

from decoder_bindings.decoder import Decoder
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel, field_validator
from tempfile import TemporaryDirectory

# wmo: 6902892 

app = FastAPI()


@app.post("/decode_float/{wmonum}")
async def hello(wmonum: str, files: list[UploadFile]):

    
    # with TemporaryDirectory(dir=".") as temp_directory:
    #     for file in files:
    #         opened_file = await file.read()
    #         (Path(temp_directory) / file.filename).write_bytes(opened_file)
    for file in files:
        print('file', file.filename)

        decoder = Decoder(
            input_files_directory=None,
            output_files_directory=None,
            decoder_conf_file="/mnt/data/config/decoder_conf.json",
        )
        decoder.decode(wmonum=wmonum,
            rsync_file=file.filename)

    return {"Hello": "World"}



# accept files via HTTP - DONE
# Can also override the config JSON with their own fields (dict update)
# We need a field to accept the WMO
# We'd also like to send back the files via a Zip.
# We also want to accept the meta/info as JSON data (not the file)
# By default just give back the NC's zipped (Can we send multiple files without zipping, if so, nice.)
# Not be root in docker-compose yml