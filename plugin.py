from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import unregister_plugin
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable
import sublime
import os
import tempfile

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit


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


class EclipseJavaDevelopmentTools(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return "jdtls"

    @classmethod
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        settings = sublime.load_settings("LSP-jdtls.sublime-settings")
        java_home = settings.get("settings").get("java.home")
        if not java_home:
            java_home = os.environ.get("JAVA_HOME")
        if java_home:
            java_executable = os.path.join(java_home, "bin", "java")
        else:
            java_executable = "java"
        return {
            "java_executable": java_executable,
            "watch_parent_process": "false" if sublime.platform() == "windows" else "true",
            "jdtls_platform": _jdtls_platform()
        }

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


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
