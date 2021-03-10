from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import Request
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable
from LSP.plugin.core.registry import LspTextCommand
from LSP.plugin.core.protocol import ExecuteCommandParams, Notification
import os
import sublime
from urllib.request import urlopen
from urllib.error import URLError
import re
import shutil
import tempfile
import tarfile
import itertools

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.views import location_to_encoded_filename, text_document_identifier


DOWNLOAD_URL = "http://download.eclipse.org/jdtls/snapshots"
LATEST_SNAPSHOT = None
SETTINGS_FILENAME = "LSP-jdtls.sublime-settings"
STORAGE_DIR = 'LSP-jdtls'
SERVER_DIR = "server"
DATA_DIR = "data"
SESSION_NAME = "jdtls"


def fetch_latest_release() -> None:
    """
    Fetches the latest release.
    """
    global LATEST_SNAPSHOT
    if not LATEST_SNAPSHOT:
        try:
            with urlopen(DOWNLOAD_URL + "/latest.txt") as f:
                data = f.read().decode('utf-8')
                version = re.search("jdt-language-server-(.*).tar.gz", data)
                LATEST_SNAPSHOT = version.group(1)
        except URLError:
            pass


def serverversion() -> Optional[str]:
    """
    Returns the version of to use. Can be None if
    no version is set in settings and no connection is available and
    and no server is available offline.
    """
    fetch_latest_release()
    settings = sublime.load_settings(SETTINGS_FILENAME)
    version = settings.get('version')
    if version:
        return version
    return LATEST_SNAPSHOT


def serverdir(storage_path) -> str:
    """
    The directory of the server.
    """
    version = serverversion()
    servers_dir = os.path.join(storage_path, SERVER_DIR)
    if version:
        return os.path.join(servers_dir, version)
    else:
        servers = os.listdir(servers_dir)
        if servers:
            return os.path.join(servers_dir, servers[0])
    raise ConnectionError("current release could not be fetched and no release is available offline")


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
    with urlopen(url) as response, open(file_name, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)


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
        for file in os.listdir(os.path.join(serverdir(cls.storage_subpath()), "plugins")):
            match = re.search("org.eclipse.equinox.launcher_(.*).jar", file)
            if match:
                launcher_version = match.group(1)
        return {
            "java_executable": java_executable,
            "watch_parent_process": "false" if sublime.platform() == "windows" else "true",
            "jdtls_platform": _jdtls_platform(),
            "serverdir": serverdir(cls.storage_subpath()),
            "datadir": os.path.join(cls.storage_subpath(), DATA_DIR),
            "launcher_version": launcher_version
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.reflist = []  # type: List[str]

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        return not os.path.isdir(serverdir(cls.storage_subpath()))

    @classmethod
    def install_or_update(cls) -> None:
        version = serverversion()
        if not version:
            return
        basedir = cls.storage_subpath()
        if os.path.isdir(basedir):
            shutil.rmtree(basedir)
        os.makedirs(basedir)
        with tempfile.TemporaryDirectory() as tempdir:
            tar_path = os.path.join(tempdir, "server.tar.gz")
            sublime.status_message("LSP-jdtls: downloading...")
            download_file(DOWNLOAD_URL + "/jdt-language-server-" + version + ".tar.gz",
                          tar_path)
            sublime.status_message("LSP-jdtls: extracting")
            tar = tarfile.open(tar_path, "r:gz")
            tar.extractall(tempdir)
            tar.close()
            for dir in os.listdir(tempdir):
                absdir = os.path.join(tempdir, dir)
                if os.path.isdir(absdir):
                    shutil.move(absdir, serverdir(cls.storage_subpath()))

    def on_pre_server_command(self, command: Mapping[str, Any], done: Callable[[], None]) -> bool:
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

    def _show_quick_panel(self, session: Session, references: List[Dict[str, Any]]) -> None:
        self.reflist = [location_to_encoded_filename(r) for r in references]
        session.window.show_quick_panel(
            self.reflist,
            self._on_ref_choice,
            sublime.KEEP_OPEN_ON_FOCUS_LOST,
            0,
            self._on_ref_highlight
        )

    def _on_ref_choice(self, index: int) -> None:
        self._open_ref_index(index, transient=False)

    def _on_ref_highlight(self, index: int) -> None:
        self._open_ref_index(index, transient=True)

    def _open_ref_index(self, index: int, transient: bool = False) -> None:
        if index != -1:
            session = self.weaksession()
            if session:
                flags = sublime.ENCODED_POSITION | sublime.TRANSIENT if transient else sublime.ENCODED_POSITION
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


class LspJdtlsStartDebugSession(LspTextCommand):
    """ Connector to Debugger.
    """

    session_name = SESSION_NAME

    def run(self, edit, id):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        builder = {}
        builder["id"] = id

        command = {"command": "vscode.java.resolveMainClass"}  # type: ExecuteCommandParams
        session.execute_command(command, False).then(lambda response: self._resolve_mainclass(builder, response))

    def _resolve_mainclass(self, builder, response):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        builder["mainClass"] = response[0]["mainClass"]
        builder["projectName"] = response[0]["projectName"]

        command = {
            "command": "vscode.java.resolveClasspath",
            "arguments": [builder["mainClass"], builder["projectName"]]
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(lambda response: self._resolve_classpath(builder, response))

    def _resolve_classpath(self, builder, response):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        builder["classPaths"] = list(itertools.chain(*response))

        command = {"command": "vscode.java.startDebugSession"}  # type: ExecuteCommandParams
        session.execute_command(command, False).then(lambda response: self._start_debug_session(builder, response))

    def _start_debug_session(self, builder, response):
        window = self.view.window()
        if window is None:
            return
        builder["port"] = response
        print(builder)
        window.run_command('debugger_lsp_jdtls_start_debugging_response', builder)


class LspJdtlsBuildWorkspace(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        params = True
        session.send_request(Request("java/buildWorkspace", params), self.on_response_async, self.on_error_async)

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
        command = {"command": "vscode.java.resolveBuildFiles"}  # type: ExecuteCommandParams
        session.execute_command(command, False).then(self._send_update_requests)

    def _send_update_requests(self, files):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        for uri in files:
            params = {"uri": uri}
            session.send_notification(Notification("java/projectConfigurationUpdate", params))


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
