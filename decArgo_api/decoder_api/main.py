"""Uvicorn entrypoint for the Decoder API.

Launches the FastAPI application defined at 'decoder_api.api:app'
when this module is executed as a script.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "decoder_api.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
