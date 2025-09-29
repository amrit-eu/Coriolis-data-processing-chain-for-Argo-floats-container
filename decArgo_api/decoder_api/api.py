import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
import os
from uuid import uuid4

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from pydantic import BaseModel, Field

from decoder_bindings.main import Decoder
from decoder_bindings.utilities.dict2json import save_info_meta_conf
from decoder_bindings.settings import Settings  # <- pydantic-settings


# -------- App & settings --------
ROOT_PATH = os.getenv("API_ROOT_PATH", "")
app = FastAPI(root_path=ROOT_PATH)


@lru_cache
def get_settings() -> Settings:
    # Lit l'environnement une seule fois (perf + stabilité)
    s = Settings()
    # Optionnel: vérifier ici l'existence/permissions de chemins critiques
    Path(s.DECODER_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    return s


# -------- Schemas --------
class DecodeRequest(BaseModel):
    wmonum: str = Field(..., description="WMO of float to decode")
    conf_dict: dict[str, Any] = Field(..., description="Decoder configuration")
    info_dict: Optional[dict[str, Any]] = Field(
        default=None, description="Information configuration file"
    )
    meta_dict: Optional[dict[str, Any]] = Field(
        default=None, description="Metadata configuration file"
    )


class DecodeResponse(BaseModel):
    status: str
    request_id: str
    float_info: dict[str, Any] | None = None
    result: str


# ---------- Utils / service ----------
def _read_upload_json(f: UploadFile | None) -> dict[str, Any] | None:
    if not f:
        return None
    try:
        raw = f.file.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Uploaded JSON must be an object")
        return data
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON file '{f.filename}': {e}"
        )


def _run_decode(
    *,
    wmonum: str,
    conf_dict: dict[str, Any],
    info_dict: dict[str, Any] | None,
    meta_dict: dict[str, Any] | None,
    settings: Settings,
) -> DecodeResponse:
    # Racine de sortie pour cet appel
    request_id = uuid4()
    request_output_root_dir = (
        Path(settings.DECODER_OUTPUT_DIR) / "api" / str(request_id)
    )
    request_output_config_dir = request_output_root_dir / "config"

    # 1) Save JSON configurations files for this execution
    try:
        float_info = save_info_meta_conf(
            config_dir=request_output_config_dir,
            float_info_dir=str(
                request_output_config_dir / "decArgo_config_floats/json_float_info"
            ),
            float_meta_dir=str(
                request_output_config_dir / "decArgo_config_floats/json_float_meta"
            ),
            info=info_dict,
            meta=meta_dict,
            decoder_conf=conf_dict,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input or save error: {e}")

    # 2) execute decoder
    try:
        decoder = Decoder(
            decoder_executable=str(settings.DECODER_EXECUTABLE),
            matlab_runtime=str(settings.MATLAB_RUNTIME),
            decoder_conf_file=str(request_output_config_dir / "decoder_conf.json"),
            # input_files_directory=str(settings.DECODER_INPUT_DIR),  # TODO: not implemented currently
            output_files_directory=str(request_output_root_dir),
            timeout_seconds=settings.DECODER_TIMEOUT,
        )
        decoder_result = decoder.decode(wmonum, capture_output=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decoder failed: {e}")

    return DecodeResponse(
        status="OK",
        request_id=str(request_id),
        float_info=float_info,
        result=decoder_result,
    )


# -------- Routes --------
@app.get("/", tags=["health"])
def app_status():
    return {"status": "OK"}


# --- Endpoint JSON ---
@app.post("/decode-float", response_model=DecodeResponse, tags=["decode"])
def decode_float_json(
    payload: DecodeRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Content-Type: application/json
    Body: { wmonum, conf_dict, info_dict?, meta_dict? }
    """
    return _run_decode(
        wmonum=payload.wmonum,
        conf_dict=payload.conf_dict,
        info_dict=payload.info_dict,
        meta_dict=payload.meta_dict,
        settings=settings,
    )


# --- Endpoint multipart (fichiers) ---
@app.post("/browse/decode-float", response_model=DecodeResponse, tags=["decode"])
async def decode_float_upload(
    wmonum: str = Form(..., description="WMO of float to decode"),
    conf_file: UploadFile = File(..., description="JSON file for conf_dict"),
    info_file: UploadFile | None = File(None, description="JSON file for info_dict"),
    meta_file: UploadFile | None = File(None, description="JSON file for meta_dict"),
    settings: Settings = Depends(get_settings),
):
    """
    Content-Type: multipart/form-data
    Fields:
      - wmonum: text
      - conf_file: required JSON file
      - info_file: optional JSON file
      - meta_file: optional JSON file
    """
    conf_dict = _read_upload_json(conf_file)
    info_dict = _read_upload_json(info_file)
    meta_dict = _read_upload_json(meta_file)

    return _run_decode(
        wmonum=wmonum,
        conf_dict=conf_dict or {},
        info_dict=info_dict,
        meta_dict=meta_dict,
        settings=settings,
    )
