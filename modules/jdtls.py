import json
import os
import re

import sublime
from LSP.plugin import (
    AbstractPlugin,
    Request,
    WorkspaceFolder,
    register_plugin,
    unregister_plugin,
)
from LSP.plugin.core.protocol import DocumentUri
from LSP.plugin.core.sessions import ExecuteCommandParams
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Any, Callable, Dict, List, Optional
from LSP.plugin.core.views import text_document_identifier

from . import installer
from .constants import (
    JDTLS_CONFIG_TO_SUBLIME_SETTING,
    SESSION_NAME,
    SETTING_JAVA_HOME,
    SETTING_JAVA_HOME_DEPRECATED,
    SETTING_LOMBOK_ENABLED,
    SETTING_PROGRESS_REPORT_ENABLED,
    VSCODE_PLUGINS,
)
from .protocol_extensions_handler import (
    language_actionableNotification,
    language_progressReport,
    language_status,
)
from .utils import (
    add_notification_handler,
    add_request_handler,
    get_settings,
    view_for_uri_async,
)
from .workspace_execute_client_command_handler import (
    workspace_executeClientCommand,
)
from .workspace_execute_command_handler import handle_client_command


@add_request_handler("workspace/executeClientCommand", workspace_executeClientCommand)
@add_notification_handler("language/status", language_status)
@add_notification_handler("language/progressReport", language_progressReport)
@add_notification_handler(
    "language/actionableNotification", language_actionableNotification
)
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
            ext_path = installer.vscode_plugin_extension_path(plugin)
            with open(os.path.join(ext_path, "package.json"), "r") as package_json:
                jars = (
                    json.load(package_json)
                    .get("contributes", {})
                    .get("javaExtensions", [])
                )
                for jar in jars:
                    abspath = os.path.abspath(
                        os.path.normpath(os.path.join(ext_path, jar))
                    )
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

        configuration.init_options.set(
            "workspaceFolders", [x.uri() for x in workspace_folders]
        )
        configuration.init_options.set("settings", configuration.settings.copy())
        configuration.init_options.set(
            "extendedClientCapabilities",
            {
                "progressReportProvider": configuration.settings.get(
                    SETTING_PROGRESS_REPORT_ENABLED
                ),
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
                "onCompletionItemSelectedCommand": "editor.action.triggerParameterHints",
            },
        )

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
        if handle_client_command(
            session,
            done,
            command["command"],
            command["arguments"] if "arguments" in command else [],
        ):
            return True
        return False

    def on_workspace_configuration(self, params: Dict, configuration: Any) -> Any:
        if (
            "section" in params
            and "scopeUri" in params
            and params["section"] in JDTLS_CONFIG_TO_SUBLIME_SETTING
        ):
            session = self.weaksession()
            if session:
                view = view_for_uri_async(session, params["scopeUri"])
                if view:
                    return view.settings().get(
                        JDTLS_CONFIG_TO_SUBLIME_SETTING[params["section"]], None
                    )
        return configuration

    def on_settings_changed(self, _) -> None:
        # Workaround for https://github.com/eclipse/eclipse.jdt.ls/issues/2365
        session = self.weaksession()
        if session:
            registration_id = "lsp-jdtls-inlayhint-workaround"
            capability_path = "inlayHintProvider"
            registration_path = capability_path + ".id"
            options = {"resolveProvider": False}
            session.capabilities.register(
                registration_id, capability_path, registration_path, options
            )
            for sv in session.session_views_async():
                sv.on_capability_added_async(registration_id, capability_path, options)


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
