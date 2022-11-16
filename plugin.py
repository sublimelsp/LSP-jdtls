from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import Request
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable

import os
import sublime
import re
import json
import sys

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.protocol import DocumentUri
from LSP.plugin.core.views import location_to_encoded_filename
from LSP.plugin.core.views import text_document_identifier

# Fix reloading for submodules
for m in list(sys.modules.keys()):
    if m.startswith(__package__ + ".") and m != __name__:
        del sys.modules[m]

from .modules.client_command_handler import execute_client_command  # noqa: E402
from .modules.test_extension_server_commands import LspJdtlsGenerateTests, LspJdtlsGotoTest, LspJdtlsRunTestAtCursor, LspJdtlsRunTestClass, LspJdtlsRunTest  # noqa: E402, F401
from .modules.debug_extension import LspJdtlsRefreshWorkspace, DebuggerJdtlsBridgeRequest  # noqa: E402, F401
from .modules.quick_input_panel import JdtlsInputCommand  # noqa: E402, F401
from .modules.utils import LspJdtlsTextCommand  # noqa: E402

from .modules.constants import DATA_DIR  # noqa: E402
from .modules.constants import SESSION_NAME  # noqa: E402
from .modules.constants import SETTINGS_FILENAME  # noqa: E402

from .modules import installer  # noqa: E402


class EclipseJavaDevelopmentTools(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    # Installation and Updates
    ##########################

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        return installer.needs_update_or_installation()

    @classmethod
    def install_or_update(cls) -> None:
        installer.install_or_update()

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
        for file in os.listdir(os.path.join(installer.jdtls_path(), "plugins")):
            match = re.search("org.eclipse.equinox.launcher_(.*).jar", file)
            if match:
                launcher_version = match.group(1)

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

        return {
            "java_executable": java_executable,
            "watch_parent_process": "false"
            if sublime.platform() == "windows"
            else "true",
            "jdtls_platform": _jdtls_platform(),
            "serverdir": installer.jdtls_path(),
            "datadir": os.path.join(installer.storage_subpath(), DATA_DIR),
            "launcher_version": launcher_version,
            "debug_plugin_path": installer.debug_plugin_jar_path(),
        }

    @classmethod
    def _enable_lombok(cls, configuration: ClientConfig):
        """
        Edits the command to enable/disable lombok.
        """
        javaagent_arg = "-javaagent:" + installer.lombok_jar_path()

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
        jarpath = os.path.join(installer.vscode_java_test_extension_path(), "extension/server")
        with open(os.path.join(installer.vscode_java_test_extension_path(), "extension/package.json"), "r") as package_json:
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
        execute_client_command(session, request_id, params["command"], params["arguments"])


class LspJdtlsBuildWorkspace(LspJdtlsTextCommand):

    def run_jdtls_command(self, edit, session: Session):
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


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
