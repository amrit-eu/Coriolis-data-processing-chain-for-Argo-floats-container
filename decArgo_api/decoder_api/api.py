"""Decoder API.

FastAPI service exposing two endpoints to run the Coriolis MATLAB-based decoder
either with a JSON payload or by uploading JSON files (multipart/form-data).

This module intentionally contains **no functional changes** to your logic.
All additions are documentation (docstrings, OpenAPI metadata, examples).
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from decoder_wrapper.main import Decoder
from decoder_wrapper.settings import Settings  # <- pydantic-settings
from decoder_wrapper.utilities.dict2json import save_info_meta_conf

# --------------------------------------------------------------------------------------
# App & settings (OpenAPI metadata only; no functional changes)
# --------------------------------------------------------------------------------------

ROOT_PATH = os.getenv("API_ROOT_PATH", "")

tags_metadata = [
    {
        "name": "health",
        "description": "Simple liveness endpoint to verify the service is running.",
    },
    {
        "name": "decode",
        "description": (
            "Endpoints to launch the MATLAB-based decoder. "
            "Choose JSON input or file-upload input. Both call the same internal service logic."
        ),
    },
]

app = FastAPI(
    root_path=ROOT_PATH,
    title="Decoder API",
    version="1.0.0",
    description=(
        "API to run the Coriolis decoder over float data.\n\n"
        "This service provides two input modalities:\n\n"
        "1) **JSON body** (`application/json`) — `/decode-float`\n"
        "2) **File uploads** (`multipart/form-data`) — `/browse/decode-float`\n\n"
        "Both endpoints produce the same structured response with run identifiers and decoder logs."
    ),
    contact={
        "name": "Decoder Team",
        "email": "team@example.org",
    },
    license_info={
        "name": "Apache-2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_tags=tags_metadata,
)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Settings are read once (from environment and defaults) and reused across requests.
    This provides stability and avoids repeated filesystem checks.
    """
    s = Settings()
    # Ensure output root exists (best effort)
    Path(s.DECODER_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    return s


# --------------------------------------------------------------------------------------
# Schemas (request/response models)
# --------------------------------------------------------------------------------------


class DecodeRequest(BaseModel):
    """Request body for JSON-based decoding.

    Attributes:
    ----------
    wmonum:
        WMO identifier of the float to decode.
    conf_dict:
        Decoder configuration (JSON object). Required.
    info_dict:
        Optional information object for the decoder.
    meta_dict:
        Optional metadata object for the decoder.
    """

    wmonum: str = Field(..., description="WMO of float to decode")
    conf_dict: dict[str, Any] = Field(..., description="Decoder configuration")
    info_dict: dict[str, Any] | None = Field(default=None, description="Information configuration file")
    meta_dict: dict[str, Any] | None = Field(default=None, description="Metadata configuration file")


class DecodeResponse(BaseModel):
    """Standard response model for a decode run.

    Attributes:
    ----------
    status:
        Status string (e.g., 'OK').
    request_id:
        Unique identifier for this decode run.
    float_info:
        Optional dictionary returned by the pre-run configuration save step.
    result:
        Raw process output (stdout/stderr) returned by the underlying decoder call.
    """

    status: str
    request_id: str
    float_info: dict[str, Any] | None = None
    result: str


# --------------------------------------------------------------------------------------
# Utilities / service (docstrings only; logic unchanged)
# --------------------------------------------------------------------------------------


def _read_upload_json(f: UploadFile | None) -> dict[str, Any] | None:
    """Read and parse a single uploaded JSON file into a Python dict.

    Parameters
    ----------
    f:
        Optional `UploadFile` handle provided by FastAPI for multipart/form-data.

    Returns:
    -------
    dict | None
        Parsed JSON object (dict) or `None` if no file is provided.

    Raises:
    ------
    HTTPException
        400 if the uploaded content is not valid JSON or not a JSON object.
    """
    if not f:
        return None
    try:
        raw = f.file.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Uploaded JSON must be an object")
        return data
    except Exception as e:  # noqa: BLE001 (keep broad to wrap any parse error)
        raise HTTPException(status_code=400, detail=f"Invalid JSON file '{f.filename}': {e}") from e


def _run_decode(
    *,
    wmonum: str,
    conf_dict: dict[str, Any],
    info_dict: dict[str, Any] | None,
    meta_dict: dict[str, Any] | None,
    settings: Settings,
) -> DecodeResponse:
    """Execute a full decode run (shared service used by both endpoints).

    Steps (unchanged):
    1) Create a unique run directory under the configured output root.
    2) Persist JSON configuration files for this run (info/meta/conf).
    3) Invoke the MATLAB-based decoder and capture its textual output.

    Parameters
    ----------
    wmonum:
        WMO identifier of the target float.
    conf_dict:
        Decoder configuration JSON object (required).
    info_dict:
        Optional information object.
    meta_dict:
        Optional metadata object.
    settings:
        Resolved service configuration (`Settings`).

    Returns:
    -------
    DecodeResponse
        Standardized response payload including run id, float info, and decoder output.

    Raises:
    ------
    HTTPException
        400 if provided JSON is invalid or cannot be persisted.
        500 if the decoder execution fails.
    """
    # Output directories for this run
    request_id = uuid4()
    request_output_root_dir = Path(settings.DECODER_OUTPUT_DIR) / "api" / str(request_id)
    request_output_config_dir = request_output_root_dir / "config"

    # Persist JSON configuration files for the decoder
    try:
        float_info = save_info_meta_conf(
            config_dir=request_output_config_dir,
            float_info_dir=str(request_output_config_dir / "decArgo_config_floats/json_float_info"),
            float_meta_dir=str(request_output_config_dir / "decArgo_config_floats/json_float_meta"),
            info=info_dict,
            meta=meta_dict,
            decoder_conf=conf_dict,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid input or save error: {e}") from e

    # Execute decoder (MATLAB-based)
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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Decoder failed: {e}") from e

    return DecodeResponse(
        status="OK",
        request_id=str(request_id),
        float_info=float_info,
        result=decoder_result,
    )


# --------------------------------------------------------------------------------------
# Routes (summaries, descriptions, and examples only; logic unchanged)
# --------------------------------------------------------------------------------------


@app.get(
    "/",
    tags=["health"],
    summary="Service health check",
    description="Returns a simple status payload indicating the service is running.",
)
def app_status():
    """Liveness probe for monitoring and quick diagnostics."""
    return {"status": "OK"}


@app.post(
    "/decode-float",
    response_model=DecodeResponse,
    tags=["decode"],
    summary="Run decoder with a JSON request body",
    description=(
        "Launches a decode run using a **JSON payload**. "
        "Provide the `wmonum` and the required `conf_dict`. "
        "`info_dict` and `meta_dict` are optional.\n\n"
        "**Content-Type:** `application/json`"
    ),
)
def decode_float_json(
    payload: DecodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """JSON-based decode entrypoint.

    Example request body:
    ```json
    {
      "wmonum": "6902892",
      "conf_dict": { "param": "value" },
      "info_dict": { "WMO": "6902892" },
      "meta_dict": {}
    }
    ```
    """
    return _run_decode(
        wmonum=payload.wmonum,
        conf_dict=payload.conf_dict,
        info_dict=payload.info_dict,
        meta_dict=payload.meta_dict,
        settings=settings,
    )


@app.post(
    "/browse/decode-float",
    response_model=DecodeResponse,
    tags=["decode"],
    summary="Run decoder by uploading JSON files (multipart/form-data)",
    description=(
        "Launches a decode run using **uploaded JSON files**. "
        "Send `wmonum` as a text field, and upload `conf_file` (required) plus "
        "`info_file`/`meta_file` (optional)."
    ),
)
async def decode_float_upload(
    # Requis : pas de default dans Annotated, pas de valeur par défaut -> requis
    wmonum: Annotated[str, Form(description="WMO of float to decode")],
    conf_file: Annotated[UploadFile, File(description="JSON file for conf_dict")],
    settings: Annotated[Settings, Depends(get_settings)],
    # Optionnels : pas de default dans File(...). Le “None” est mis après le `=`.
    info_file: Annotated[UploadFile | None, File(description="JSON file for info_dict")] = None,
    meta_file: Annotated[UploadFile | None, File(description="JSON file for meta_dict")] = None,
):
    """Multipart/form-data decode entrypoint.

    Example `curl`:
    ```bash
    curl -X POST "http://localhost:8000/browse/decode-float" \
      -F wmonum=6902892 \
      -F conf_file=@path/to/decoder_conf.json \
      -F info_file=@path/to/info.json \
      -F meta_file=@path/to/meta.json
    ```
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
