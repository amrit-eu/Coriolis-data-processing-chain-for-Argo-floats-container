# Decoder API

## Python FastAPI

This Python package exists to access the Coriolis Decoder via Python API.

### Development

- Create vitual environment

```bash
conda create -n argo-decoder-api python=3.12 poetry
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
python3 -u decoder_api/main.py
```

access API documentation at <http://localhost:8080/docs>

- Request API with Documentation GUI ou with `curl`

```bash
# JSON content
curl -X POST "http://localhost:8000/decode-float" \
-H "Content-Type: application/json" \
-d '{"wmonum":"6904182","conf_dict":'"$(cat tests/data/config/decoder_conf_for_6904182.json)"', "info_dict":'"$(cat ../decArgo_demo/config/decArgo_config_floats/json_float_info/6904182_300125061965370_info.json)"', "meta_dict":'"$(cat ../decArgo_demo/config/decArgo_config_floats/json_float_meta/6904182_meta.json)"'}'

# Browsing files
curl -X POST "http://localhost:8000/browse/decode-float" \
-F wmonum=6904182 -F conf_file=@tests/data/config/decoder_conf_for_6904182.json \
-F info_file=@../decArgo_demo/config/decArgo_config_floats/json_float_info/6904182_300125061965370_info.json \
-F meta_file=@../decArgo_demo/config/decArgo_config_floats/json_float_meta/6904182_meta.json
```

- Run unit tests

```bash
pytest
```

- Run integration tests

```bash
pytest -m "integration and matlab"
```
