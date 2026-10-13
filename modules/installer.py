from __future__ import annotations

import os
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable
from urllib.request import urlopen

import sublime
from LSP.plugin import ST_STORAGE_PATH

from .constants import (
    DATA_DIR,
    INSTALL_DIR,
    JDTLS_TAR_URL_FILE,
    JDTLS_URL,
    LOMBOK_URL,
    LOMBOK_VERSION,
    STORAGE_DIR,
    VSCODE_PLUGINS,
)

# File Download / Extraction
############################


def download_file(url: str, file_name: str | Path) -> None:
    with urlopen(url) as response, open(file_name, "wb") as out_file:
        shutil.copyfileobj(response, out_file)


def _extract_file(
    url: str,
    path: str | Path,
    open_function: Callable[[str], zipfile.ZipFile] | Callable[[str], tarfile.TarFile],
) -> None:
    with tempfile.TemporaryDirectory() as download_dir:
        compressed_file = os.path.join(download_dir, "compressed_file")
        download_file(url, compressed_file)
        uncompress_dir = os.path.join(download_dir, "uncompress_dir")
        os.makedirs(uncompress_dir)
        with open_function(compressed_file) as compressed_file:
            compressed_file.extractall(uncompress_dir)
        # Make writable before delete due to issue with latest jdt-*.tar.gz:
        # https://github.com/sublimelsp/LSP-jdtls/pull/58
        _make_all_files_writable(uncompress_dir)
        shutil.move(uncompress_dir, path)


def _make_all_files_writable(root_dir: str) -> None:
    """
    Make's all files in folder writeable
    """
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                # Skip if already writable
                if os.access(path, os.W_OK):
                    continue
                # Add user write bit
                new_mode = path.stat().st_mode | stat.S_IWRITE
                os.chmod(path, new_mode)
            except Exception as e:
                print(f"Failed on {path}: {e}")


def extract_zip(url: str, path: str | Path) -> None:
    """
    Extracts the zip at `url` to `path`.
    The zip is extracted into `path` if it already exists.
    """
    _extract_file(url, path, lambda x: zipfile.ZipFile(x, "r"))


def extract_tar(url: str, path: str | Path) -> None:
    """
    Extracts the tar at `url` to `path`.
    The tar is extracted into `path` if it already exists.
    """
    _extract_file(url, path, lambda x: tarfile.open(x, "r:gz"))


# Path definitions
##################


def storage_subpath() -> Path:
    return Path(ST_STORAGE_PATH, STORAGE_DIR)


def install_path() -> Path:
    return storage_subpath() / INSTALL_DIR


def jdtls_path(jdtls_version: str) -> Path:
    return install_path() / f"jdtls-{jdtls_version}"


def jdtls_data_path() -> Path:
    return storage_subpath() / DATA_DIR


def vscode_plugin_path(plugin_name: str) -> Path:
    plugin = VSCODE_PLUGINS[plugin_name]
    return install_path() / f"{plugin_name}-{plugin['version']}"


def vscode_plugin_extension_path(plugin_name: str) -> Path:
    """Path to the folder containing the package.json"""
    plugin = VSCODE_PLUGINS[plugin_name]
    subpath = plugin["extension_path"].format(version=plugin["version"])
    return (vscode_plugin_path(plugin_name) / subpath).resolve()


def lombok_jar_path() -> Path:
    return install_path() / f"lombok-{LOMBOK_VERSION}.jar"


# Install / Update
###################


def needs_update_or_installation(jdtls_version: str) -> bool:
    result = not jdtls_path(jdtls_version).is_dir()
    result |= not lombok_jar_path().is_file()
    for plugin in VSCODE_PLUGINS:
        result |= not vscode_plugin_path(plugin).is_dir()
    return result


def install_or_update(jdtls_version: str) -> None:
    basedir = storage_subpath()
    if basedir.is_dir():
        # Make writable before delete due to issue with latest jdt-*.tar.gz:
        # https://github.com/sublimelsp/LSP-jdtls/pull/58
        def del_rw(action, name, exc):
            os.chmod(name, stat.S_IWRITE)
            os.remove(name)
        shutil.rmtree(basedir, onerror=del_rw)
    basedir.mkdir(parents=True)

    # fmt: off
    sublime.status_message("LSP-jdtls: downloading jdtls...")
    with urlopen(JDTLS_TAR_URL_FILE.format(version=jdtls_version)) as latest:
        extract_tar(JDTLS_URL.format(version=jdtls_version, tar=latest.read().decode().rstrip()), jdtls_path(jdtls_version))
    sublime.status_message("LSP-jdtls: downloading lombok...")
    download_file(LOMBOK_URL.format(version=LOMBOK_VERSION), lombok_jar_path())
    for plugin_name, plugin in VSCODE_PLUGINS.items():
        sublime.status_message(f"LSP-jdtls: downloading {plugin_name}...")
        extract_zip(plugin["url"].format(version=plugin["version"]), vscode_plugin_path(plugin_name))
    # fmt: on
