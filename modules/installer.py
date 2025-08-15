import os
import shutil
import stat
import tarfile
import tempfile
import zipfile
from urllib.request import urlopen
from pathlib import Path

import sublime
from LSP.plugin.core.typing import Callable, Union
from LSP.plugin.core.constants import ST_STORAGE_PATH

from .constants import (
    DATA_DIR,
    INSTALL_DIR,
    JDTLS_TAR_URL_FILE,
    JDTLS_URL,
    JDTLS_VERSION,
    LOMBOK_URL,
    LOMBOK_VERSION,
    SETTINGS_FILENAME,
    STORAGE_DIR,
    VSCODE_PLUGINS,
)


def _jdtls_version() -> str:
    version = sublime.load_settings(SETTINGS_FILENAME).get("version")
    return version or JDTLS_VERSION


# File Download / Extraction
############################


def download_file(url: str, file_name: str) -> None:
    with urlopen(url) as response, open(file_name, "wb") as out_file:
        shutil.copyfileobj(response, out_file)


def _extract_file(
    url: str,
    path: str,
    open_function: Union[
        Callable[[str], zipfile.ZipFile], Callable[[str], tarfile.TarFile]
    ],
):
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

def _make_all_files_writable(root_dir):
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

def extract_zip(url: str, path: str):
    """
    Extracts the zip at `url` to `path`.
    The zip is extracted into `path` if it already exists.
    """
    _extract_file(url, path, lambda x: zipfile.ZipFile(x, "r"))


def extract_tar(url: str, path: str):
    """
    Extracts the tar at `url` to `path`.
    The tar is extracted into `path` if it already exists.
    """
    _extract_file(url, path, lambda x: tarfile.open(x, "r:gz"))


# Path definitions
##################


def storage_subpath() -> str:
    return os.path.join(ST_STORAGE_PATH, STORAGE_DIR)


def install_path() -> str:
    return os.path.join(storage_subpath(), INSTALL_DIR)


def jdtls_path() -> str:
    return os.path.join(
        install_path(), "jdtls-{version}".format(version=_jdtls_version())
    )


def jdtls_data_path() -> str:
    return os.path.join(storage_subpath(), DATA_DIR)


def vscode_plugin_path(plugin_name: str) -> str:
    plugin = VSCODE_PLUGINS[plugin_name]
    return os.path.join(
        install_path(),
        "{name}-{version}".format(name=plugin_name, version=plugin["version"]),
    )


def vscode_plugin_extension_path(plugin_name: str) -> str:
    """Path to the folder containing the package.json"""
    plugin = VSCODE_PLUGINS[plugin_name]
    subpath = plugin["extension_path"].format(version=plugin["version"])
    return os.path.normpath(os.path.join(vscode_plugin_path(plugin_name), subpath))


def lombok_jar_path() -> str:
    return os.path.join(
        install_path(),
        "lombok-{version}.jar".format(version=LOMBOK_VERSION),
    )


# Install / Update
###################


def needs_update_or_installation() -> bool:
    result = not os.path.isdir(jdtls_path())
    result |= not os.path.isfile(lombok_jar_path())
    for plugin in VSCODE_PLUGINS:
        result |= not os.path.isdir(vscode_plugin_path(plugin))
    return result


def install_or_update() -> None:
    version = _jdtls_version()
    basedir = storage_subpath()
    if os.path.isdir(basedir):
        # Make writable before delete due to issue with latest jdt-*.tar.gz:
        # https://github.com/sublimelsp/LSP-jdtls/pull/58
        def del_rw(action, name, exc):
            os.chmod(name, stat.S_IWRITE)
            os.remove(name)
        shutil.rmtree(basedir, onerror=del_rw)
    os.makedirs(basedir)

    # fmt: off
    sublime.status_message("LSP-jdtls: downloading jdtls...")
    with urlopen(JDTLS_TAR_URL_FILE.format(version=version)) as latest:
        extract_tar(JDTLS_URL.format(version=version, tar=latest.read().decode().rstrip()), jdtls_path())
    sublime.status_message("LSP-jdtls: downloading lombok...")
    download_file(LOMBOK_URL.format(version=LOMBOK_VERSION), lombok_jar_path())
    for plugin_name, plugin in VSCODE_PLUGINS.items():
        sublime.status_message("LSP-jdtls: downloading {name}...".format(name=plugin_name))
        extract_zip(plugin["url"].format(version=plugin["version"]), vscode_plugin_path(plugin_name))
    # fmt: on