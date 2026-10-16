"""Tests for fin_tracker.config."""

import pytest

from fin_tracker.config import PATH_PROJECT_ROOT, PATH_RAW_DATA, find_project_root


def test_find_project_root_walks_up_to_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").touch()
    path_nested = tmp_path / "a" / "b"
    path_nested.mkdir(parents=True)
    assert find_project_root(path_nested) == tmp_path


def test_find_project_root_raises_without_pyproject(tmp_path, monkeypatch):
    # Pretend no ancestor has a pyproject.toml
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    with pytest.raises(FileNotFoundError):
        find_project_root(tmp_path)


def test_default_paths_point_inside_the_repo():
    assert (PATH_PROJECT_ROOT / "pyproject.toml").exists()
    assert PATH_RAW_DATA == PATH_PROJECT_ROOT / "data" / "raw"
