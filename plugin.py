from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import Request
from LSP.plugin import Notification
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable, Union

import os
import sublime
from urllib.request import urlopen
import re
import shutil
import tempfile
import tarfile
import zipfile
import json

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.protocol import DocumentUri
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.registry import LspWindowCommand, LspTextCommand
from LSP.plugin.core.views import location_to_encoded_filename
from LSP.plugin.core.views import text_document_identifier

from .modules.client_command_handler import ask_client_for_choice

# fmt: off
LOMBOK_VERSION = "1.18.24"
LOMBOK_URL = "https://repo1.maven.org/maven2/org/projectlombok/lombok/{version}/lombok-{version}.jar"
DEBUG_PLUGIN_VERSION = "0.40.0"
DEBUG_PLUGIN_URL = "https://repo1.maven.org/maven2/com/microsoft/java/com.microsoft.java.debug.plugin/{version}/com.microsoft.java.debug.plugin-{version}.jar"
JDTLS_VERSION = "1.14.0-202207211651"
JDTLS_URL = "http://download.eclipse.org/jdtls/snapshots/jdt-language-server-{version}.tar.gz"
VSCODE_JAVA_TEST_EXTENSION_VERSION = "0.37.1"
VSCODE_JAVA_TEST_EXTENSION_URL = "https://github.com/microsoft/vscode-java-test/releases/download/{version}/vscjava.vscode-java-test-{version}.vsix"

SETTINGS_FILENAME = "LSP-jdtls.sublime-settings"
STORAGE_DIR = "LSP-jdtls"
SESSION_NAME = "jdtls"
INSTALL_DIR = "server"
DATA_DIR = "data"
# fmt: on


def _jdtls_version() -> str:
    version = sublime.load_settings(SETTINGS_FILENAME).get("version")
    return version or JDTLS_VERSION


def _jdtls_platform() -> str:
    p = sublime.platform()
    if p == "windows":
        return "win"
    elif p == "osx":
        return "mac"
    elif p == "linux":
        return "linux"
    else:
        raise ValueError("unknown platform: {}".format(p))


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
        shutil.move(uncompress_dir, path)


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


class EclipseJavaDevelopmentTools(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    # Path definitions
    ##################

    @classmethod
    def storage_subpath(cls) -> str:
        return os.path.join(cls.storage_path(), STORAGE_DIR)

    @classmethod
    def install_path(cls) -> str:
        return os.path.join(cls.storage_subpath(), INSTALL_DIR)

    @classmethod
    def jdtls_path(cls) -> str:
        return os.path.join(
            cls.install_path(), "jdtls-{version}".format(version=_jdtls_version())
        )

    @classmethod
    def vscode_java_test_extension_path(cls) -> str:
        return os.path.join(
            cls.install_path(),
            "vscode-java-test-{version}".format(
                version=VSCODE_JAVA_TEST_EXTENSION_VERSION
            ),
        )

    @classmethod
    def lombok_jar_path(cls) -> str:
        return os.path.join(
            cls.install_path(),
            "lombok-{version}.jar".format(version=DEBUG_PLUGIN_VERSION),
        )

    @classmethod
    def debug_plugin_jar_path(cls) -> str:
        return os.path.join(
            cls.install_path(),
            "com.microsoft.java.debug.plugin-{version}.jar".format(
                version=DEBUG_PLUGIN_VERSION
            ),
        )

    # Installation and Updates
    ##########################

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        result = not os.path.isdir(cls.jdtls_path())
        result |= not os.path.isfile(cls.lombok_jar_path())
        result |= not os.path.isfile(cls.debug_plugin_jar_path())
        result |= not os.path.isdir(cls.vscode_java_test_extension_path())
        return result

    @classmethod
    def install_or_update(cls) -> None:
        version = _jdtls_version()
        basedir = cls.storage_subpath()
        if os.path.isdir(basedir):
            shutil.rmtree(basedir)
        os.makedirs(basedir)

        # fmt: off
        sublime.status_message("LSP-jdtls: downloading jdtls...")
        extract_tar(JDTLS_URL.format(version=version), cls.jdtls_path())
        sublime.status_message("LSP-jdtls: downloading lombok...")
        download_file(LOMBOK_URL.format(version=LOMBOK_VERSION), cls.lombok_jar_path())
        sublime.status_message("LSP-jdtls: downloading debug plugin...")
        download_file(DEBUG_PLUGIN_URL.format(version=DEBUG_PLUGIN_VERSION), cls.debug_plugin_jar_path())
        sublime.status_message("LSP-jdtls: downloading test extension...")
        extract_zip(VSCODE_JAVA_TEST_EXTENSION_URL.format(version=VSCODE_JAVA_TEST_EXTENSION_VERSION), cls.vscode_java_test_extension_path())
        # fmt: on

    # Server configuration
    ######################

    @classmethod
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        settings = sublime.load_settings(SETTINGS_FILENAME)
        java_home = settings.get("settings").get("java.home")
        if not java_home:
            java_home = os.environ.get("JAVA_HOME")
        if java_home:
            java_executable = os.path.join(java_home, "bin", "java")
        else:
            java_executable = "java"

        launcher_version = ""
        for file in os.listdir(os.path.join(cls.jdtls_path(), "plugins")):
            match = re.search("org.eclipse.equinox.launcher_(.*).jar", file)
            if match:
                launcher_version = match.group(1)
        return {
            "java_executable": java_executable,
            "watch_parent_process": "false"
            if sublime.platform() == "windows"
            else "true",
            "jdtls_platform": _jdtls_platform(),
            "serverdir": cls.jdtls_path(),
            "datadir": os.path.join(cls.storage_subpath(), DATA_DIR),
            "launcher_version": launcher_version,
            "debug_plugin_path": cls.debug_plugin_jar_path(),
        }

    @classmethod
    def _enable_lombok(cls, configuration: ClientConfig):
        """
        Edits the command to enable/disable lombok.
        """
        javaagent_arg = "-javaagent:" + cls.lombok_jar_path()

        # Prevent adding the argument multiple times
        if (
            configuration.settings.get("jdtls.enableLombok")
            and javaagent_arg not in configuration.command
        ):
            jar_index = configuration.command.index("-jar")
            configuration.command.insert(jar_index, javaagent_arg)
        elif (
            not configuration.settings.get("jdtls.enableLombok")
            and javaagent_arg in configuration.command
        ):
            configuration.command.remove(javaagent_arg)

    @classmethod
    def _enable_test_extension(cls, configuration: ClientConfig):
        jarpath = os.path.join(cls.vscode_java_test_extension_path(), "extension/server")
        with open(os.path.join(cls.vscode_java_test_extension_path(), "extension/package.json"), "r") as package_json:
            jars = json.load(package_json)["contributes"]["javaExtensions"]
            bundles = configuration.init_options.get("bundles")
            for jar in jars:
                abspath = os.path.join(jarpath, jar[len("./server/"):])
                if jar.endswith(".jar") and os.path.isfile(abspath):
                    if abspath not in bundles:
                        bundles += [abspath]
            configuration.init_options.set("bundles", bundles)

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: List[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> Optional[str]:
        cls._enable_lombok(configuration)
        cls._enable_test_extension(configuration)
        return None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.reflist = []  # type: List[str]

    def on_open_uri_async(
        self, uri: DocumentUri, callback: Callable[[str, str, str], None]
    ) -> bool:
        if not uri.startswith("jdt:"):
            return False
        session = self.weaksession()
        if not session:
            return False
        # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/protocol.ts#L105-L107
        # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/providerDispatcher.ts#L61-L76
        # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/providerDispatcher.ts#L27-L28
        session.send_request_async(
            Request(
                "java/classFileContents", text_document_identifier(uri), progress=True
            ),
            lambda resp: callback(uri, resp, "Packages/Java/Java.sublime-syntax"),
            lambda err: callback(
                "ERROR", str(err), "Packages/Text/Plain text.tmLanguage"
            ),
        )
        return True

    # Custom command handling
    #########################

    def on_pre_server_command(
        self, command: Mapping[str, Any], done: Callable[[], None]
    ) -> bool:
        session = self.weaksession()
        if not session:
            return False
        cmd = command["command"]
        if cmd == "java.apply.workspaceEdit":
            changes = parse_workspace_edit(command["arguments"][0])
            window = session.window
            sublime.set_timeout(
                lambda: apply_workspace_edit(window, changes).then(
                    lambda _: sublime.set_timeout_async(done)
                )
            )
            return True
        elif cmd == "java.show.references":
            self._show_quick_panel(session, command["arguments"][2])
            done()
            return True
        return False

    def _show_quick_panel(
        self, session: Session, references: List[Dict[str, Any]]
    ) -> None:
        self.reflist = [location_to_encoded_filename(r) for r in references]  # type: ignore
        session.window.show_quick_panel(
            self.reflist,
            self._on_ref_choice,
            sublime.KEEP_OPEN_ON_FOCUS_LOST,
            0,
            self._on_ref_highlight,
        )

    def _on_ref_choice(self, index: int) -> None:
        self._open_ref_index(index, transient=False)

    def _on_ref_highlight(self, index: int) -> None:
        self._open_ref_index(index, transient=True)

    def _open_ref_index(self, index: int, transient: bool = False) -> None:
        if index != -1:
            session = self.weaksession()
            if session:
                flags = (
                    sublime.ENCODED_POSITION | sublime.TRANSIENT
                    if transient
                    else sublime.ENCODED_POSITION
                )
                session.window.open_file(self.reflist[index], flags)

    # notification and request handlers

    def m_language_status(self, params: Any) -> None:
        session = self.weaksession()
        if not session:
            return
        message = params.get("message")
        if not message:
            return
        session.window.status_message(message)

    def m_workspace_executeClientCommand(self, params: Any, request_id) -> None:
        session = self.weaksession()
        if not session:
            return

        command_name = params["command"]
        arguments = params["arguments"]

        client_command_handler = {
            "_java.test.askClientForChoice": ask_client_for_choice
        }

        if command_name in client_command_handler:
            client_command_handler[command_name](session, request_id, *arguments)
        else:
            print("{}: no command handler for client command {}".format(SESSION_NAME, command_name))


class DebuggerJdtlsBridgeRequest(LspWindowCommand):
    """Connector bridge to Debugger allowing to send requests to the language server.

    The response is sent back using the specified callback_command (window command).
    The callback command must have the interface def callback(id, error, resp),
    if error is not None then it contains a reason else resp is not None.
    """

    session_name = SESSION_NAME

    def run(self, id, callback_command, method, params, progress=False):
        session = self.session()
        response_args = {"id": id, "error": None, "resp": None}
        if not session:
            response_args["error"] = "No JDTLS session found."
            self.window.run_command(callback_command, response_args)
            return

        def _on_request_success(resp):
            response_args["resp"] = resp
            self.window.run_command(callback_command, response_args)

        def _on_request_error(err):
            response_args["error"] = str(err)
            self.window.run_command(callback_command, response_args)

        session.send_request_async(
            Request(method, params, progress=progress),
            _on_request_success,
            _on_request_error,
        )


class LspJdtlsBuildWorkspace(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        params = True
        session.send_request(
            Request("java/buildWorkspace", params),
            self.on_response_async,
            self.on_error_async,
        )

    def on_response_async(self, response):
        window = self.view.window()
        if window is None:
            return
        if response == 0:
            window.status_message("LSP-jdtls: Build failed")
        elif response == 1:
            window.status_message("LSP-jdtls: Build succeeded")
        elif response == 2:
            window.status_message("LSP-jdtls: Build ended with error")
        elif response == 3:
            window.status_message("LSP-jdtls: Build cancelled")

    def on_error_async(self, error):
        pass


class LspJdtlsRefreshWorkspace(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        command = {
            "command": "vscode.java.resolveBuildFiles"
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(self._send_update_requests)

    def _send_update_requests(self, files):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        for uri in files:
            params = {"uri": uri}
            session.send_notification(
                Notification("java/projectConfigurationUpdate", params)
            )


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
