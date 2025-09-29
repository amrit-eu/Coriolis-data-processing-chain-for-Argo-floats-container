# Decoder API

## Python Bindings

This Python package exists to access the Coriolis Decoder via Python.

### Development

- Create vitual environment

```bash
conda create -n decoder-argo python=3.12 poetry
cd decArgo_api
```

- Install required dependecies

```bash
poetry install
```

- Run application bindings on predefine float

```bash
python3 -u decoder_bindings/main.py
```

- Run application API

```bash
python3 -u decoder_bindings/main.py
```

- Run unit tests

```bash
pytest
```

- Run integration tests

```bash
pytest -m "integration and matlab"
```

## FastAPI
