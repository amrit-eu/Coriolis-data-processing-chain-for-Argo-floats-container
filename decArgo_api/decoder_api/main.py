import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "decoder_api.api:app",  # adapte au chemin réel de ton fichier FastAPI
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
