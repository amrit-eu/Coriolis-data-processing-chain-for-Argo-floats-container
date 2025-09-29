from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
import os
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException
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
    output_dir: str
    config_dir: str
    float_info: dict[str, Any] | None = None


# -------- Routes --------
@app.get("/", tags=["health"])
def app_status():
    return {"status": "OK"}


@app.post("/decoder/decode-float", response_model=DecodeResponse, tags=["decode"])
def decode_files(payload: DecodeRequest, settings: Settings = Depends(get_settings)):
    """
    Lance un décodage synchrone. Pour des runs longs, envisager un BackgroundTask
    ou une file (Celery/RQ) à la place.
    """
    request_id = uuid4()
    request_root: Path = Path(settings.DECODER_OUTPUT_DIR) / "api" / str(request_id)
    try:
        request_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create output dirs: {e}"
        )

    # 1) Persister les JSON de conf/meta/info pour le décodeur
    try:
        float_info = save_info_meta_conf(
            config_dir=str(request_root),
            float_info_dir=str(
                request_root
                / "decArgo_config_floats/json_float_info"
            ),
            float_meta_dir=str(
                request_root / "decArgo_config_floats/json_float_meta"
            ),
            info=payload.info_dict,
            meta=payload.meta_dict,
            decoder_conf=payload.conf_dict,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input or save error: {e}")

    # 2) Exécuter le décodeur
    try:
        decoder = Decoder(
            decoder_executable=str(settings.DECODER_EXECUTABLE),
            matlab_runtime=str(settings.MATLAB_RUNTIME),
            decoder_conf_file=str(settings.DECODER_CONFIG_DIR / "decoder_conf.json"),
            input_files_directory=str(settings.DECODER_INPUT_DIR),
            output_files_directory=str(request_root),
            timeout_seconds=settings.DECODER_TIMEOUT,  # ← configurable
        )
        decoder.decode(payload.wmonum)
    except Exception as e:
        # Tu peux logger ici e avec stacktrace si besoin
        raise HTTPException(status_code=500, detail=f"Decoder failed: {e}")

    return DecodeResponse(
        status="OK",
        request_id=str(request_id),
        output_dir=str(request_root),
        config_dir=str(settings.DECODER_CONFIG_DIR),
        float_info=float_info,
    )
