from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import Request
from LSP.plugin import Notification
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable

import os
import sublime
from urllib.request import urlopen
import re
import shutil
import tempfile
import tarfile

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.protocol import DocumentUri, WorkspaceFolder
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.registry import LspWindowCommand, LspTextCommand
from LSP.plugin.core.views import location_to_encoded_filename
from LSP.plugin.core.views import text_document_identifier


LOMBOK_VERSION = "1.18.24"
LOMBOK_URL = "https://repo1.maven.org/maven2/org/projectlombok/lombok/{version}/lombok-{version}.jar"
DEBUG_PLUGIN_VERSION = "0.40.0"
DEBUG_PLUGIN_URL = "https://repo1.maven.org/maven2/com/microsoft/java/com.microsoft.java.debug.plugin/{version}/com.microsoft.java.debug.plugin-{version}.jar"
JDTLS_VERSION = "1.14.0-202207211651"
JDTLS_URL = "http://download.eclipse.org/jdtls/snapshots/jdt-language-server-{version}.tar.gz"
SETTINGS_FILENAME = "LSP-jdtls.sublime-settings"
STORAGE_DIR = "LSP-jdtls"
SESSION_NAME = "jdtls"
SERVER_DIR = "server"
DATA_DIR = "data"


def serverversion() -> str:
    """
    Returns the version of to use. Can be None if
    no version is set in settings and no connection is available and
    and no server is available offline.
    """
    settings = sublime.load_settings(SETTINGS_FILENAME)
    version = settings.get("version")
    if version:
        return version
    return JDTLS_VERSION


def serverdir(storage_path) -> str:
    """
    The directory of the server.
    """
    version = serverversion()
    servers_dir = os.path.join(storage_path, SERVER_DIR)
    return os.path.join(servers_dir, version)


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


def download_file(url, file_name) -> None:
    with urlopen(url) as response, open(file_name, "wb") as out_file:
        shutil.copyfileobj(response, out_file)


def lombok_path(storage_path):
    servers_dir = os.path.join(storage_path, SERVER_DIR)
    return os.path.join(
        servers_dir, "lombok-{version}.jar".format(version=DEBUG_PLUGIN_VERSION)
    )


def debug_plugin_path(storage_path):
    servers_dir = os.path.join(storage_path, SERVER_DIR)
    return os.path.join(
        servers_dir,
        "com.microsoft.java.debug.plugin-{version}.jar".format(
            version=DEBUG_PLUGIN_VERSION
        ),
    )


class EclipseJavaDevelopmentTools(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    @classmethod
    def storage_subpath(cls) -> str:
        return os.path.join(cls.storage_path(), STORAGE_DIR)

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
        for file in os.listdir(
            os.path.join(serverdir(cls.storage_subpath()), "plugins")
        ):
            match = re.search("org.eclipse.equinox.launcher_(.*).jar", file)
            if match:
                launcher_version = match.group(1)
        return {
            "java_executable": java_executable,
            "watch_parent_process": "false"
            if sublime.platform() == "windows"
            else "true",
            "jdtls_platform": _jdtls_platform(),
            "serverdir": serverdir(cls.storage_subpath()),
            "datadir": os.path.join(cls.storage_subpath(), DATA_DIR),
            "launcher_version": launcher_version,
            "debug_plugin_path": debug_plugin_path(cls.storage_subpath()),
        }

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: List[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> Optional[str]:
        javaagent_arg = "-javaagent:" + lombok_path(cls.storage_subpath())
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
        return None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.reflist = []  # type: List[str]

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        result = not os.path.isdir(serverdir(cls.storage_subpath()))
        result |= not os.path.isfile(lombok_path(cls.storage_subpath()))
        result |= not os.path.isfile(debug_plugin_path(cls.storage_subpath()))
        return result

    @classmethod
    def install_or_update(cls) -> None:
        version = serverversion()
        basedir = cls.storage_subpath()
        if os.path.isdir(basedir):
            shutil.rmtree(basedir)
        os.makedirs(basedir)

        with tempfile.TemporaryDirectory() as tempdir:
            tar_path = os.path.join(tempdir, "server.tar.gz")
            sublime.status_message("LSP-jdtls: downloading server...")
            download_file(JDTLS_URL.format(version=version), tar_path)
            sublime.status_message("LSP-jdtls: extracting server...")
            tar = tarfile.open(tar_path, "r:gz")
            tar.extractall(tempdir)
            tar.close()
            for dir in os.listdir(tempdir):
                absdir = os.path.join(tempdir, dir)
                if os.path.isdir(absdir):
                    shutil.move(absdir, serverdir(basedir))

        sublime.status_message("LSP-jdtls: downloading lombok...")
        download_file(LOMBOK_URL.format(version=LOMBOK_VERSION), lombok_path(basedir))
        sublime.status_message("LSP-jdtls: downloading debug plugin...")
        download_file(
            DEBUG_PLUGIN_URL.format(version=DEBUG_PLUGIN_VERSION),
            debug_plugin_path(basedir),
        )

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
