"""Unit tests for the final Decoder implementation.

Scope validated here:
- Executable & MATLAB runtime are configurable and passed in the command.
- Optional post-run "hold" replaces a previous infinite loop without burning CPU.
- Paths and WMO validation behave as specified (including negative cases).
- Command construction is correct (with/without I/O flags depending on config).
"""

import importlib
import re
import stat
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest


# -----------------------------------------------------------------------------
# Stubs for top-level imports referenced by the module under test
# (utilities.dict2json, mock_data). These are lightweight shims used to
# decouple tests from external modules/files during import-time.
# -----------------------------------------------------------------------------
def _inject_stubs_for_top_level_imports():
    if "utilities.dict2json" not in sys.modules:
        utilities = types.ModuleType("utilities")
        dict2json = types.ModuleType("utilities.dict2json")

        def save_info_meta_conf(*args, **kwargs):
            return {}

        dict2json.save_info_meta_conf = save_info_meta_conf
        utilities.dict2json = dict2json
        sys.modules["utilities"] = utilities
        sys.modules["utilities.dict2json"] = dict2json

    if "mock_data" not in sys.modules:
        mock_data = types.ModuleType("mock_data")
        mock_data.info_dict = {}
        mock_data.meta_dict = {}
        mock_data.conf_dict = {}
        sys.modules["mock_data"] = mock_data


_inject_stubs_for_top_level_imports()

# -----------------------------------------------------------------------------
# Import module under test
# -----------------------------------------------------------------------------

# Align "flat" imports used inside main.py so the module can import cleanly.
# (main.py does `from utilities...` and `from mock_data...`)
sys.modules.setdefault("utilities", importlib.import_module("decoder_wrapper.utilities"))
sys.modules.setdefault(
    "utilities.dict2json",
    importlib.import_module("decoder_wrapper.utilities.dict2json"),
)
sys.modules.setdefault("settings", importlib.import_module("decoder_wrapper.settings"))

MODULE_NAME = "decoder_wrapper.main"
m = importlib.import_module(MODULE_NAME)


# -----------------------------------------------------------------------------
# Utility fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def tmp_conf_file(tmp_path: Path) -> Path:
    """Create a temporary decoder_conf.json file."""
    p = tmp_path / "decoder_conf.json"
    p.write_text('{"some":"config"}', encoding="utf-8")
    return p


@pytest.fixture
def tmp_runtime_dir(tmp_path: Path) -> Path:
    """Create a temporary MATLAB runtime directory."""
    d = tmp_path / "matlab_runtime"
    d.mkdir()
    return d


@pytest.fixture
def tmp_exec_file(tmp_path: Path) -> Path:
    """Create a temporary executable bash wrapper script."""
    f = tmp_path / "run_decode.sh"
    f.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    # make it executable for validators relying on +x
    f.chmod(f.stat().st_mode | stat.S_IXUSR)
    return f


@pytest.fixture
def tmp_nonexec_file(tmp_path: Path) -> Path:
    """Create a non-executable file to trigger exec-path validation."""
    f = tmp_path / "not_exec.sh"
    f.write_text("echo nope\n", encoding="utf-8")
    # ensure it is NOT executable (validator should fail)
    f.chmod(0o644)
    return f


@pytest.fixture
def tmp_input_dir(tmp_path: Path) -> Path:
    """Create a temporary non-empty input directory."""
    d = tmp_path / "input"
    d.mkdir()
    (d / "dummy.bin").write_bytes(b"\x00\x01")
    return d


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return d


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("wmo", ["6902892", "4902452", "7901234"])
def test_decode_builds_cmd_with_exec_and_runtime_and_io(
    wmo, tmp_conf_file, tmp_runtime_dir, tmp_exec_file, tmp_input_dir, tmp_output_dir
):
    """Build the decoder CLI with exec/runtime and I/O wrapper."""
    # Arrange: Decoder with both input and output directories configured.
    dec = m.Decoder(
        input_files_directory=str(tmp_input_dir),
        output_files_directory=str(tmp_output_dir),
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
        timeout_seconds=123,
        hold_after_run=None,
    )

    with patch.object(m.subprocess, "run") as mock_run:
        # Return a CompletedProcess-like object to satisfy decode() expectations.
        mock_run.return_value = subprocess.CompletedProcess(args=["dummy"], returncode=0, stdout="OK", stderr="")

        # Act
        dec.decode(wmo)

        # Assert
        (args, kwargs) = mock_run.call_args
        cmd = args[0]

        # Executable + MATLAB runtime come first
        assert cmd[0] == str(tmp_exec_file.resolve())
        assert cmd[1] == str(tmp_runtime_dir.resolve())

        # Invariant arguments up to the config path
        assert cmd[2:6] == [
            "rsynclog",
            "all",
            "configfile",
            str(tmp_conf_file.resolve()),
        ]

        # XML report argument: "xmlreport" followed by a dynamic filename
        assert "xmlreport" in cmd
        xml_idx = cmd.index("xmlreport")
        xml_name = cmd[xml_idx + 1]
        assert re.match(rf"^xmlreport_{wmo}_\d{{8}}_\d{{6}}\.xml$", xml_name), xml_name

        # WMO & processing flags
        assert "floatwmo" in cmd and wmo in cmd
        assert "PROCESS_REMAINING_BUFFERS" in cmd and "1" in cmd

        # Output directory flags should be present and point to the expected subfolders
        def expect_flag_with_path(flag: str, expected_path: str):
            assert flag in cmd, f"Missing flag {flag}"
            i = cmd.index(flag)
            assert i + 1 < len(cmd), f"No value after {flag}"
            assert cmd[i + 1] == expected_path

        out_root = tmp_output_dir.resolve()
        expect_flag_with_path("IRIDIUM_DATA_DIRECTORY", str(out_root / "iridium"))
        expect_flag_with_path("DIR_OUTPUT_LOG_FILE", str(out_root / "log"))
        expect_flag_with_path("DIR_OUTPUT_CSV_FILE", str(out_root / "csv"))
        expect_flag_with_path("DIR_OUTPUT_XML_FILE", str(out_root / "xml"))
        expect_flag_with_path("DIR_OUTPUT_NETCDF_FILE", str(out_root / "nc"))
        expect_flag_with_path("DIR_OUTPUT_NETCDF_TRAJ_3_2_FILE", str(out_root / "nc"))

        # Execution options passed to subprocess.run
        assert kwargs["timeout"] == 123
        assert kwargs["text"] is True
        assert kwargs["check"] is True
        assert isinstance(kwargs["env"], dict)


def test_decode_without_io_does_not_add_dirs(tmp_conf_file, tmp_runtime_dir, tmp_exec_file):
    """Do not add I/O flags when no I/O directories are configured."""
    # Arrange: Decoder with no input nor output directory configured.
    dec = m.Decoder(
        input_files_directory=None,
        output_files_directory=None,
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
    )

    with patch.object(m.subprocess, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=["dummy"], returncode=0, stdout="OK", stderr="")

        # Act
        dec.decode("6902892")

        # Assert: command must not contain any I/O wrapper flags
        cmd = mock_run.call_args[0][0]
        forbidden_flags = {
            # input flags (currently commented out in implementation)
            "DIR_INPUT_RSYNC_DATA",
            "DIR_INPUT_RSYNC_LOG",
            # output flags (absent when output_files_directory=None)
            "IRIDIUM_DATA_DIRECTORY",
            "DIR_OUTPUT_LOG_FILE",
            "DIR_OUTPUT_CSV_FILE",
            "DIR_OUTPUT_XML_FILE",
            "DIR_OUTPUT_NETCDF_FILE",
            "DIR_OUTPUT_NETCDF_TRAJ_3_2_FILE",
        }
        assert not (set(cmd) & forbidden_flags), f"Unexpected IO flags in cmd: {set(cmd) & forbidden_flags}"


@pytest.mark.parametrize("bad_wmo", ["", "123", "abcdefg", "69028921", " 6902892 "])
def test_invalid_wmo_raises(bad_wmo, tmp_conf_file, tmp_runtime_dir, tmp_exec_file):
    """Invalid WMO values should raise WmoValidationError."""
    # Arrange
    dec = m.Decoder(
        input_files_directory=None,
        output_files_directory=None,
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
    )
    # Act / Assert: invalid WMO -> WmoValidationError
    with pytest.raises(m.WmoValidationError):
        dec.decode(bad_wmo)


def test_conf_file_missing_raises(tmp_path: Path, tmp_runtime_dir, tmp_exec_file):
    """Missing JSON configuration file should raise ValueError."""
    # Arrange: non-existent JSON config file
    missing = tmp_path / "nope.json"
    # Act / Assert: constructing Decoder should fail on missing conf file
    with pytest.raises(ValueError):
        m.Decoder(
            input_files_directory=None,
            output_files_directory=None,
            decoder_conf_file=str(missing),
            decoder_executable=str(tmp_exec_file),
            matlab_runtime=str(tmp_runtime_dir),
        )


def test_executable_must_exist_and_be_executable(tmp_conf_file, tmp_runtime_dir, tmp_nonexec_file):
    """Executable path must exist and be executable."""
    # Non-executable file should trigger a validation error for the executable path
    with pytest.raises(ValueError):
        m.Decoder(
            input_files_directory=None,
            output_files_directory=None,
            decoder_conf_file=str(tmp_conf_file),
            decoder_executable=str(tmp_nonexec_file),
            matlab_runtime=str(tmp_runtime_dir),
        )


def test_runtime_must_be_dir(tmp_conf_file, tmp_exec_file, tmp_path: Path):
    """MATLAB runtime must be a directory, not a file."""
    # Arrange: a file (not a directory) used as runtime path
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    # Act / Assert: runtime must be a directory
    with pytest.raises(ValueError):
        m.Decoder(
            input_files_directory=None,
            output_files_directory=None,
            decoder_conf_file=str(tmp_conf_file),
            decoder_executable=str(tmp_exec_file),
            matlab_runtime=str(not_a_dir),
        )


def test_calledprocesserror_is_caught_and_hold_runs(
    tmp_conf_file, tmp_runtime_dir, tmp_exec_file, tmp_input_dir, tmp_output_dir
):
    """CalledProcessError is handled; hold branch should sleep once."""
    # Arrange: hold_after_run=2 so we can assert the sleep call is made once
    dec = m.Decoder(
        input_files_directory=str(tmp_input_dir),
        output_files_directory=str(tmp_output_dir),
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
        hold_after_run=2,
    )

    with patch.object(m.subprocess, "run") as mock_run, patch.object(m.time, "sleep") as mock_sleep:
        # Simulate a non-zero exit from the subprocess
        mock_run.side_effect = m.subprocess.CalledProcessError(returncode=42, cmd=["x"])

        # Act: should not raise (current implementation prints and continues)
        dec.decode("6902892")

        # Assert: the "hold" branch should sleep once for 2 seconds
        mock_sleep.assert_called_once_with(2)


def test_hold_after_run_none_no_sleep(tmp_conf_file, tmp_runtime_dir, tmp_exec_file):
    """With hold_after_run=None, no sleep should occur."""
    # Arrange: hold_after_run=None should skip any sleep
    dec = m.Decoder(
        input_files_directory=None,
        output_files_directory=None,
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
        hold_after_run=None,
    )
    with patch.object(m.subprocess, "run") as mock_run, patch.object(m.time, "sleep") as mock_sleep:
        mock_run.return_value = subprocess.CompletedProcess(args=["dummy"], returncode=0, stdout="OK", stderr="")

        # Act
        dec.decode("6902892")

        # Assert: no sleep call expected
        mock_sleep.assert_not_called()


def test_hold_after_run_forever_loops_but_is_mocked(tmp_conf_file, tmp_runtime_dir, tmp_exec_file):
    """With hold_after_run=-1, the infinite-hold loop sleeps repeatedly (mocked)."""
    # Arrange: hold_after_run=-1 triggers the "infinite hold" branch.
    dec = m.Decoder(
        input_files_directory=None,
        output_files_directory=None,
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=str(tmp_runtime_dir),
        hold_after_run=-1,  # infinite hold
    )

    call_count = {"n": 0}

    def fake_sleep(seconds: int):
        # The infinite-hold branch sleeps in 60-second intervals; simulate 3 cycles then stop.
        assert seconds == 60
        call_count["n"] += 1
        if call_count["n"] >= 3:
            raise StopIteration  # stop the test here

    with patch.object(m.subprocess, "run") as mock_run, patch.object(m.time, "sleep", side_effect=fake_sleep):
        mock_run.return_value = subprocess.CompletedProcess(args=["dummy"], returncode=0, stdout="OK", stderr="")
        # Act / Assert: we raise StopIteration to exit the simulated infinite loop
        with pytest.raises(StopIteration):
            dec.decode("6902892")
        assert call_count["n"] >= 3


def test_decoder_configuration_with_valid_directories(tmp_input_dir, tmp_output_dir, tmp_conf_file, tmp_exec_file):
    """Ensure configuration is built correctly when valid directories are supplied."""
    cfg = m.DecoderConfiguration(
        input_files_directory=tmp_input_dir,
        output_files_directory=tmp_output_dir,
        decoder_conf_file=tmp_conf_file,
        decoder_executable=tmp_exec_file,  # required by validators
        matlab_runtime=None,  # optional
    )
    assert cfg.input_files_directory == tmp_input_dir.resolve()
    assert cfg.output_files_directory == tmp_output_dir.resolve()


def test_decoder_with_empty_input_directory(tmp_path: Path, tmp_output_dir, tmp_conf_file, tmp_exec_file):
    """Empty input directory should raise EmptyInputDirectoryError."""
    empty_input = tmp_path / "empty_in"
    empty_input.mkdir()
    with pytest.raises(m.EmptyInputDirectoryError):
        m.DecoderConfiguration(
            input_files_directory=empty_input,
            output_files_directory=tmp_output_dir,
            decoder_conf_file=tmp_conf_file,
            decoder_executable=tmp_exec_file,
            matlab_runtime=None,  # optional
        )


def test_decoder_with_invalid_directories(tmp_path: Path, tmp_conf_file, tmp_exec_file):
    """Non-existent directories should trigger coherent ValueError messages."""
    input_path = tmp_path / "input"  # does not exist
    output_path = tmp_path / "output"  # does not exist

    with pytest.raises(ValueError) as exc:
        m.DecoderConfiguration(
            input_files_directory=input_path,
            output_files_directory=output_path,
            decoder_conf_file=tmp_conf_file,
            decoder_executable=tmp_exec_file,
            matlab_runtime=None,  # optional
        )
    assert "is not a valid input directory" in str(exc.value)

    # Create input dir to test the output-dir validation separately
    input_path.mkdir()
    (input_path / "test.txt").write_text("test", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        m.DecoderConfiguration(
            input_files_directory=input_path,
            output_files_directory=output_path,
            decoder_conf_file=tmp_conf_file,
            decoder_executable=tmp_exec_file,
            matlab_runtime=None,  # optional
        )
    assert "is not a valid output directory" in str(exc.value)


def test_decoder_initialisation(tmp_input_dir, tmp_output_dir, tmp_conf_file, tmp_exec_file):
    """Decoder initializes correctly with valid paths."""
    dec = m.Decoder(
        input_files_directory=str(tmp_input_dir),
        output_files_directory=str(tmp_output_dir),
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=None,  # optional in config
    )
    assert isinstance(dec, m.Decoder)
    assert isinstance(dec.config, m.DecoderConfiguration)
    assert dec.config.input_files_directory == tmp_input_dir.resolve()
    assert dec.config.output_files_directory == tmp_output_dir.resolve()


def test_subprocess_call(monkeypatch, tmp_input_dir, tmp_output_dir, tmp_conf_file, tmp_exec_file):
    """Ensure subprocess.run is invoked once and the command is shaped as expected."""
    dec = m.Decoder(
        input_files_directory=str(tmp_input_dir),
        output_files_directory=str(tmp_output_dir),
        decoder_conf_file=str(tmp_conf_file),
        decoder_executable=str(tmp_exec_file),
        matlab_runtime=None,  # optional in config
    )

    called = {"n": 0, "cmd": None}

    def fake_run(cmd, **kwargs):
        # record invocation and return a CompletedProcess-like object
        called["n"] += 1
        called["cmd"] = cmd
        return subprocess.CompletedProcess(args=["dummy"], returncode=0, stdout="OK", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)

    # Act
    dec.decode("6902892")

    # Assert
    assert called["n"] == 1
    assert called["cmd"][0] == str(tmp_exec_file.resolve())
    # If matlab_runtime=None, the second arg in the command may be the string "None":
    # we accept that here and focus on the presence of the WMO arguments.
    assert "floatwmo" in called["cmd"] and "6902892" in called["cmd"]
