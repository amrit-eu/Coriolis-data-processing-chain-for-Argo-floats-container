"""Tests d'intégration du décodeur.

Lance réellement le décodeur sur 3 flotteurs, compare les sorties avec des
références validées (golden outputs). Toute divergence = échec.
Lancer explicitement:  pytest -m "integration and matlab" -q
"""

import importlib
import os
import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pytest

# --- Markers: disabled by default ---
pytestmark = [pytest.mark.integration, pytest.mark.matlab]

# --- Parameters: 3 floats (wmo + configuration + reference outputs) --------------------------
# From data in the decArgo_demo directory
# Must provide:
#   DECODER_EXECUTABLE, MATLAB_RUNTIME, DECODER_INPUT_DIR
WMOS = [
    (
        "6902892",
        "./tests/data/config/decoder_conf_for_6902892.json",
        "./tests/data/ref/6902892",
    ),
    (
        "6903014",
        "./tests/data/config/decoder_conf_for_6903014.json",
        "./tests/data/ref/6903014",
    ),
    (
        "6904182",
        "./tests/data/config/decoder_conf_for_6904182.json",
        "./tests/data/ref/6904182",
    ),
]


# --- Helpers: environment checks, fail fast with motivated skip ---------------
def _need_file(env: str) -> Path:
    p = os.getenv(env)
    if not p:
        pytest.skip(f"Missing env var: {env}")
    path = Path(p)
    if not path.exists():
        pytest.skip(f"{env} points to missing path: {path}")
    return path


def _need_dir(env: str) -> Path:
    p = _need_file(env)
    if not p.is_dir():
        pytest.skip(f"{env} is not a directory: {p}")
    return p


def _need_exec(env: str) -> Path:
    p = _need_file(env)
    if not os.access(p, os.X_OK):
        pytest.skip(f"{env} is not executable: {p}")
    return p


# --- Import tested module + alias flat imports used in main.py ---
# The module 'decoder_bindings.main' uses "flat" imports (utilities, mock_data).
# We create aliases to the package submodules so that the import works.
sys.modules.setdefault("utilities", importlib.import_module("decoder_wrapper.utilities"))
sys.modules.setdefault(
    "utilities.dict2json",
    importlib.import_module("decoder_wrapper.utilities.dict2json"),
)

from decoder_wrapper.main import Decoder  # noqa: E402


# --- Robust NetCDF comparison (fail on any difference by default) ----------
def _assert_netcdf_equal(test_path: Path, ref_path: Path, *, atol: float, rtol: float) -> None:
    """Comparer deux fichiers NetCDF.

    Vérifie :
      - dimensions (noms, tailles)
      - variables (noms, dtypes, shapes, valeurs)
      - attributs globaux (hors liste 'volatile')
    Échec si la moindre différence est détectée.
    """
    try:
        from netCDF4 import Dataset
    except Exception as e:
        pytest.skip(f"netCDF4 not available: {e}")

    volatile_globals = {
        "history",
        "date_created",
        "creation_date",
        "last_update",
        "date_update",
        "uuid",
        "checksum",
        "processing_history",
        "file_generation_time",
    }

    with Dataset(test_path, "r") as tds, Dataset(ref_path, "r") as rds:
        # Dimensions
        assert set(tds.dimensions) == set(rds.dimensions), "Different dimension names"
        for name in tds.dimensions:
            assert len(tds.dimensions[name]) == len(rds.dimensions[name]), f"Dimension size mismatch: {name}"

        # Variables
        assert set(tds.variables) == set(rds.variables), "Different variable names"
        for vname in tds.variables:
            tv = tds.variables[vname]
            rv = rds.variables[vname]
            # dtype + shape
            assert tv.dtype == rv.dtype, f"dtype mismatch for var {vname}"
            assert tv.shape == rv.shape, f"shape mismatch for var {vname}"
            # values (with tolerances for numeric)
            tdata = np.array(tv[:])
            rdata = np.array(rv[:])
            if np.issubdtype(tv.dtype, np.number):
                # ma/masks -> fill with NaN for comparison
                if np.ma.isMaskedArray(tdata):
                    tdata = tdata.filled(np.nan)
                if np.ma.isMaskedArray(rdata):
                    rdata = rdata.filled(np.nan)
                # any difference beyond tolerances = failure
                assert np.allclose(tdata, rdata, atol=atol, rtol=rtol, equal_nan=True), f"value mismatch in var {vname}"
            else:
                # strings, bytes: strict equality
                assert np.array_equal(tdata, rdata), f"value mismatch in var {vname}"

        # Global attributes (excluding volatile ones)
        tga = {k: getattr(tds, k) for k in tds.ncattrs() if k not in volatile_globals}
        rga = {k: getattr(rds, k) for k in rds.ncattrs() if k not in volatile_globals}
        assert tga == rga, "global attributes mismatch (non-volatile)"


def _iter_nc_files(dirpath: Path) -> Iterable[Path]:
    return sorted(dirpath.rglob("*.nc"))


def _iter_nc(dirpath: Path) -> Iterable[Path]:
    return sorted(dirpath.rglob("*.nc"))


def _compare_dirs_nc(test_dir: Path, ref_dir: Path, *, atol: float, rtol: float) -> None:
    """Comparer l'ensemble des fichiers NetCDF produits à la référence.

    - mêmes fichiers (noms relatifs)
    - contenu égal (cf. `_assert_netcdf_equal`)
    """
    # map by relative path (to support identical subdirectories)
    t_map = {p.relative_to(test_dir): p for p in _iter_nc_files(test_dir)}
    r_map = {p.relative_to(ref_dir): p for p in _iter_nc_files(ref_dir)}

    assert set(t_map.keys()) == set(r_map.keys()), (
        "Different NetCDF file sets:\n"
        f"Only in test: {sorted(set(t_map.keys()) - set(r_map.keys()))}\n"
        f"Only in ref : {sorted(set(r_map.keys()) - set(t_map.keys()))}"
    )

    for rel in sorted(t_map.keys()):
        _assert_netcdf_equal(t_map[rel], r_map[rel], atol=atol, rtol=rtol)


# ========================== Test A: successful execution =============================
@pytest.mark.parametrize("wmo, conf_file, ref_dir", WMOS)
def test_decode_produces_netcdf(tmp_path: Path, wmo: str, conf_file: str, ref_dir: str):
    """Vérifie que le décodeur produit au moins un fichier NetCDF pour le WMO donné."""
    exec_path = _need_exec("DECODER_EXECUTABLE")
    runtime_dir = _need_dir("MATLAB_RUNTIME")
    timeout = int(os.getenv("DECODER_TIMEOUT", "1800"))

    out_dir = Path(f"../decArgo_demo/output/nc/{wmo}")

    dec = Decoder(
        input_files_directory=None,  # from configuration file
        output_files_directory=None,  # from configuration file
        decoder_conf_file=str(conf_file),
        decoder_executable=str(exec_path),
        matlab_runtime=str(runtime_dir),
        timeout_seconds=timeout,
        hold_after_run=None,
    )

    dec.decode(wmo)

    produced = list(_iter_nc(out_dir))
    assert produced, f"Aucun NetCDF produit pour WMO {wmo} dans {out_dir}"


# TODO: Compare results to output from decoder in DAC infrastructure ?
# ========================== Test B: comparison ==============================
# @pytest.mark.parametrize("wmo, conf_file, ref_dir", WMOS)
# def test_decode_outputs_match_reference(
#     tmp_path: Path, wmo: str, conf_file: str, ref_dir: str
# ):
#     exec_path = _need_exec("DECODER_EXECUTABLE")
#     runtime_dir = _need_dir("MATLAB_RUNTIME")
#     input_dir = _need_dir("DECODER_INPUT_DIR")
#     conf_file = _need_file(conf_file)
#     timeout = int(os.getenv("DECODER_TIMEOUT", "1800"))
#
#     atol = float(os.getenv("NC_ATOL", "0"))
#     rtol = float(os.getenv("NC_RTOL", "0"))
#     timeout = int(os.getenv("DECODER_TIMEOUT", "1800"))
#
#     out_dir = tmp_path / f"out_{wmo}"
#     out_dir.mkdir()
#
#     dec = Decoder(
#         input_files_directory=str(input_dir),
#         output_files_directory=str(out_dir),
#         decoder_conf_file=str(conf_file),
#         decoder_executable=str(exec_path),
#         matlab_runtime=str(runtime_dir),
#         timeout_seconds=timeout,
#         hold_after_run=None,
#     )
#
#     dec.decode(wmo)
#
#     _compare_dirs_nc(out_dir, ref_dir, atol=atol, rtol=rtol)
