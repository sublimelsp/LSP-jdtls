from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import Request
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.sessions import ExecuteCommandParams
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Optional, Any, List, Dict, Callable

import os
import sublime
import sublime_plugin
import re
import json
import sys
import shutil

# TODO: Not part of the public API :(
from LSP.plugin.core.protocol import DocumentUri
from LSP.plugin.core.views import text_document_identifier

# Fix reloading for submodules
for m in list(sys.modules.keys()):
    if m.startswith(__package__ + ".") and m != __name__:
        del sys.modules[m]

from .modules.client_command_handler import handle_client_command, handle_client_command_request  # noqa: E402
from .modules.test_extension_server_commands import LspJdtlsGenerateTests, LspJdtlsGotoTest, LspJdtlsRunTestAtCursor, LspJdtlsRunTestClass, LspJdtlsRunTest  # noqa: E402, F401
from .modules.debug_extension import LspJdtlsRefreshWorkspace, DebuggerJdtlsBridgeRequest  # noqa: E402, F401
from .modules.quick_input_panel import JdtlsInputCommand  # noqa: E402, F401
from .modules.utils import get_settings, LspJdtlsTextCommand  # noqa: E402

from .modules.constants import SETTING_JAVA_HOME, SETTING_JAVA_HOME_DEPRECATED, SETTING_LOMBOK_ENABLED, SESSION_NAME, VSCODE_PLUGINS  # noqa: E402

from .modules.protocol_extensions_handler import handle_actionable_notification  # noqa: E402

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
        settings = get_settings()

        java_home = settings.get("settings").get(SETTING_JAVA_HOME)
        if not java_home:
            java_home = settings.get("settings").get(SETTING_JAVA_HOME_DEPRECATED)
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
            "datadir": installer.jdtls_data_path(),
            "launcher_version": launcher_version,
        }

    @classmethod
    def _enable_lombok(cls, configuration: ClientConfig):
        """
        Edits the command to enable/disable lombok.
        """
        javaagent_arg = "-javaagent:" + installer.lombok_jar_path()

        # Prevent adding the argument multiple times
        if (
            configuration.settings.get(SETTING_LOMBOK_ENABLED)
            and javaagent_arg not in configuration.command
        ):
            jar_index = configuration.command.index("-jar")
            configuration.command.insert(jar_index, javaagent_arg)
        elif (
            not configuration.settings.get(SETTING_LOMBOK_ENABLED)
            and javaagent_arg in configuration.command
        ):
            configuration.command.remove(javaagent_arg)

    @classmethod
    def _insert_bundles(cls, configuration: ClientConfig):
        bundles = configuration.init_options.get("bundles") or []
        for plugin in VSCODE_PLUGINS:
            ext_path = os.path.join(installer.vscode_plugin_path(plugin), "extension")
            with open(os.path.join(ext_path, "package.json"), "r") as package_json:
                jars = json.load(package_json).get("contributes", {}).get("javaExtensions", [])
                for jar in jars:
                    abspath = os.path.abspath(os.path.normpath(os.path.join(ext_path, jar)))
                    if abspath not in bundles:
                        bundles.append(abspath)
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
        cls._insert_bundles(configuration)

        configuration.init_options.set("workspaceFolders", [x.uri() for x in workspace_folders])
        configuration.init_options.set("settings", configuration.settings.copy())
        configuration.init_options.set("extendedClientCapabilities", {
            "progressReportProvider": False,
            "classFileContentsSupport": False,
            "overrideMethodsPromptSupport": False,
            "hashCodeEqualsPromptSupport": False,
            "advancedOrganizeImportsSupport": False,
            "generateToStringPromptSupport": False,
            "advancedGenerateAccessorsSupport": False,
            "generateConstructorsPromptSupport": False,
            "generateDelegateMethodsPromptSupport": False,
            "advancedExtractRefactoringSupport": False,
            "inferSelectionSupport": [],
            "moveRefactoringSupport": False,
            "clientHoverProvider": False,
            "clientDocumentSymbolProvider": False,
            "gradleChecksumWrapperPromptSupport": False,
            "resolveAdditionalTextEditsSupport": False,
            "advancedIntroduceParameterRefactoringSupport": False,
            "actionableRuntimeNotificationSupport": True,
            "shouldLanguageServerExitOnShutdown": True,
            "onCompletionItemSelectedCommand": "editor.action.triggerParameterHints"
        })

        # configuration.init_options.set("triggerFiles", configuration.settings)

        return None

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
        self, command: ExecuteCommandParams, done: Callable[[], None]
    ) -> bool:
        session = self.weaksession()
        if not session:
            return False
        if handle_client_command(session, done, command["command"], command["arguments"] if "arguments" in command else []):
            return True
        return False

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
        handle_client_command_request(session, request_id, params["command"], params["arguments"])

    def m_language_actionableNotification(self, params: Any) -> None:
        session = self.weaksession()
        if not session:
            return
        handle_actionable_notification(session, params)


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


class JdtlsClearData(sublime_plugin.TextCommand):
    def run(self, edit) -> None:
        if sublime.ok_cancel_dialog("Are you sure you want to clear " + installer.jdtls_data_path()):
            if os.path.exists(installer.jdtls_data_path()):
                shutil.rmtree(installer.jdtls_data_path())
                self.view.run_command("lsp_restart_server", {"config_name": SESSION_NAME})


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
