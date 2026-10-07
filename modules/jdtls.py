from __future__ import annotations

import json
import os
import re
from functools import partial
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import sublime
from LSP.plugin import (
    ClientResponse,
    Error,
    LspPlugin,
    OnPreStartContext,
    Promise,
    Request,
    command_handler,
    notification_handler,
    request_handler,
    text_document_identifier,
    uri_handler,
)
from LSP.plugin.core.views import location_to_encoded_filename
from LSP.protocol import LSPAny, TextDocumentIdentifier, WorkspaceEdit
from typing_extensions import override

from . import installer
from .constants import (
    JDTLS_CONFIG_TO_SUBLIME_SETTING,
    JDTLS_VERSION,
    SETTING_ENABLE_NULL_ANALYSIS,
    SETTING_JAVA_HOME,
    SETTING_JAVA_HOME_DEPRECATED,
    SETTING_LOMBOK_ENABLED,
    SETTING_PROGRESS_REPORT_ENABLED,
    VSCODE_PLUGINS,
)
from .installer import jdtls_data_path, jdtls_path, lombok_jar_path, vscode_plugin_extension_path
from .protocol import ActionableNotification, FeatureStatus, ProgressReport, StatusReport
from .protocol_extensions_handler import (
    language_actionableNotification,
    language_progressReport,
    language_status,
)
from .utils import (
    set_lsp_project_setting,
    view_for_uri_async,
)
from .workspace_execute_client_command_handler import workspace_executeClientCommand

if TYPE_CHECKING:
    from LSP.plugin import ClientConfig
    from LSP.protocol import DocumentUri, ExecuteCommandParams


class EclipseJavaDevelopmentTools(LspPlugin):
    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        jdtls_version = cls._jdtls_version(context.configuration)
        if installer.needs_update_or_installation(jdtls_version):
            installer.install_or_update(jdtls_version)

        settings = context.configuration.settings
        java_home = settings.get(SETTING_JAVA_HOME)
        if not java_home:
            java_home = settings.get(SETTING_JAVA_HOME_DEPRECATED)
        if not java_home:
            java_home = os.environ.get("JAVA_HOME")

        if java_home:
            java_executable = os.path.join(java_home, "bin", "java")
        else:
            java_executable = "java"

        launcher_version = ""
        for file in os.listdir(jdtls_path(jdtls_version) / "plugins"):
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
                raise ValueError(f"unknown platform: {p}")

        context.variables.update({
            "java_executable": java_executable,
            "watch_parent_process": "false" if sublime.platform() == "windows" else "true",
            "jdtls_platform": _jdtls_platform(),
            "serverdir": str(jdtls_path(jdtls_version)),
            "datadir": str(jdtls_data_path()),
            "launcher_version": launcher_version,
        })

        configuration = context.configuration

        cls._enable_lombok(configuration)
        cls._insert_bundles(configuration)

        configuration.initialization_options.set(
            "workspaceFolders", [x.uri() for x in context.workspace_folders]
        )
        configuration.initialization_options.set("settings", configuration.settings.copy())
        configuration.initialization_options.set(
            "extendedClientCapabilities",
            {
                "progressReportProvider": configuration.settings.get(
                    SETTING_PROGRESS_REPORT_ENABLED
                ),
                "classFileContentsSupport": True,
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

        # configuration.initialization_options.set("triggerFiles", configuration.settings)

    @override
    def on_pre_send_response_async(self, response: ClientResponse) -> None:
        if response["method"] == "workspace/configuration" and (session := self.weaksession()):
            for i, item in enumerate(response["params"]["items"]):
                if (
                    "section" in item
                    and "scopeUri" in item
                    and item["section"] in JDTLS_CONFIG_TO_SUBLIME_SETTING
                ):
                    view = view_for_uri_async(session, item["scopeUri"])
                    if view:
                        response["result"][i] = view.settings().get(
                            JDTLS_CONFIG_TO_SUBLIME_SETTING[item["section"]], None
                        )

    # Server configuration
    ######################

    @classmethod
    def _jdtls_version(cls, configuration: ClientConfig) -> str:
        return configuration.root_settings.get('version') or JDTLS_VERSION

    @classmethod
    def _enable_lombok(cls, configuration: ClientConfig):
        """
        Edits the command to enable/disable lombok.
        """
        javaagent_arg = f"-javaagent:{lombok_jar_path()}"

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
        bundles = configuration.initialization_options.get("bundles") or []
        # Skip jars that jdtls already ships (e.g. ASM) to avoid duplicate bundle errors
        server_jars = set(os.listdir(jdtls_path(cls._jdtls_version(configuration)) / "plugins"))
        for plugin in VSCODE_PLUGINS:
            ext_path = vscode_plugin_extension_path(plugin)
            with open(ext_path / "package.json", "r") as package_json:
                jars = (
                    json.load(package_json)
                    .get("contributes", {})
                    .get("javaExtensions", [])
                )
                for jar in jars:
                    if os.path.basename(jar) in server_jars:
                        continue
                    abspath = os.path.abspath(ext_path / jar)
                    if abspath not in bundles:
                        bundles.append(abspath)
        configuration.initialization_options.set("bundles", bundles)

    @uri_handler('jdt')
    def on_handle_jdt_uri_async(self, uri: DocumentUri, flags: sublime.NewFileFlags) -> Promise[sublime.Sheet | None]:
        if session := self.weaksession():
            # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/protocol.ts#L105-L107
            # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/providerDispatcher.ts#L61-L76
            # https://github.com/redhat-developer/vscode-java/blob/9f32875a67352487f5c414bb7fef04c9b00af89d/src/providerDispatcher.ts#L27-L28
            return session.send_request_task(
                Request[TextDocumentIdentifier, str](
                    "java/classFileContents", text_document_identifier(uri), progress=True
                ),
            ).then(partial(self.handle_class_file_contents, uri))
        return Promise.resolve(None)

    def handle_class_file_contents(self, uri: str, result: str | Error) -> Promise[sublime.Sheet | None]:
        if session := self.weaksession():
            if isinstance(result, Error):
                title = "ERROR"
                contents = str(result)
                syntax = "Packages/Text/Plain text.tmLanguage"
            else:
                title = urlparse(uri).path
                contents = result
                syntax = "Packages/Java/Java.sublime-syntax"
            return session.open_scratch_buffer(title, contents, syntax).then(lambda view: view.sheet())
        return Promise.resolve(None)

    # Custom command handling
    #########################

    @command_handler('java.compile.nullAnalysis.setMode')
    def handle_java_compile_nullAnalysis_setMode(self, arguments: list[FeatureStatus] | None) -> Promise[None]:
        if arguments and (session := self.weaksession()):
            status = arguments[0]
            mode = "automatic" if status == FeatureStatus.automatic else "disabled"
            set_lsp_project_setting(session.window, SETTING_ENABLE_NULL_ANALYSIS, mode)
        return Promise.resolve(None)

    @command_handler('java.apply.workspaceEdit')
    def handle_java_apply_workspaceEdit(self, arguments: list[WorkspaceEdit] | None) -> Promise[None]:
        if arguments and (session := self.weaksession()):
            changes = arguments[0]
            return session.apply_workspace_edit_async(changes).then(lambda _: None)
        return Promise.resolve(None)

    @command_handler('java.show.references')
    def handle_java_show_references(self, arguments: list[Any] | None) -> Promise[None]:
        if arguments and (session := self.weaksession()):
            reflist: list[str] = []

            def _open_ref_index(index: int, transient: bool = False) -> None:
                if index != -1:
                    flags = (
                        sublime.ENCODED_POSITION | sublime.TRANSIENT
                        if transient
                        else sublime.ENCODED_POSITION
                    )
                    session.window.open_file(reflist[index], flags)

            def _on_ref_choice(index: int) -> None:
                _open_ref_index(index, transient=False)

            def _on_ref_highlight(index: int) -> None:
                _open_ref_index(index, transient=True)

            reflist = [location_to_encoded_filename(r) for r in arguments[2]]
            session.window.show_quick_panel(
                reflist,
                _on_ref_choice,
                sublime.KEEP_OPEN_ON_FOCUS_LOST,
                0,
                _on_ref_highlight,
            )

        return Promise.resolve(None)

    # Workaround for https://github.com/eclipse/eclipse.jdt.ls/issues/2362
    @command_handler('java.completion.onDidSelect')
    def handle_java_completion_onDidSelect(self, arguments: list[LSPAny] | None) -> Promise[None]:
        return Promise.resolve(None)

    # Custom server notifications/requests handling
    ###############################################

    @request_handler("workspace/executeClientCommand")
    def on_workspace_execute_client_command(self, params: ExecuteCommandParams) -> Promise[Any]:
        return workspace_executeClientCommand(params)

    @notification_handler("language/status")
    def on_language_status(self, params: StatusReport) -> None:
        if session := self.weaksession():
            language_status(session, params)

    @notification_handler("language/progressReport")
    def on_language_progress_report(self, params: ProgressReport) -> None:
        if session := self.weaksession():
            language_progressReport(session, params)

    @notification_handler("language/actionableNotification")
    def on_language_actionable_notification(self, params: ActionableNotification) -> None:
        if session := self.weaksession():
            language_actionableNotification(session, params)


def plugin_loaded() -> None:
    EclipseJavaDevelopmentTools.register()


def plugin_unloaded() -> None:
    EclipseJavaDevelopmentTools.unregister()
