"""API Entrypoint."""

import logging
import tempfile

from fastapi import FastAPI, UploadFile
from fastapi.responses import StreamingResponse

from decoder_bindings.decoder import Decoder, DecoderError
from decoder_bindings.file_manager import FileManager, FileManagerError
from decoder_bindings.zip_nc_files import ZipNCFiles, ZipNCFilesError

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.post("/decode_float/{wmonum}")
async def decode_float(wmonum: str, files: list[UploadFile]):
    """Invoke the decoder and return a ZIP file of the decoded NC files.

    Args:
        wmonum: The WMONUM of the raw files to be decoded.
        files: A list of files to be decoded.

    Returns: A zipfile, or a dict containing an error message.
    """
    logging.info("Running for WMONUM: %s", wmonum)
    logging.info("Running for Files: %s", files)
    try:
        rsync_file_name = FileManager(files).run()

        with tempfile.TemporaryDirectory(dir="/mnt/data") as temporary_output_directory:
            decoder = Decoder(
                input_files_directory=None,
                output_files_directory=temporary_output_directory,
                decoder_conf_file="/mnt/data/config/decoder_conf.json",
            )
            decoder.decode(wmonum=wmonum, rsync_file=rsync_file_name)
            zipfile = ZipNCFiles(output_location=temporary_output_directory, wmonum=wmonum).zip_all_nc_files()

    except (FileManagerError, ZipNCFilesError, DecoderError):
        return {"Message": "Zip file not generated. Check the logs for more information."}
    else:
        return StreamingResponse(
            zipfile, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={wmonum}.zip"}
        )
