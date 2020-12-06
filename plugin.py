from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin.core.typing import Optional, Any, List, Dict, Mapping, Callable
import os
import sublime
import tempfile

# TODO: Not part of the public API :(
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.views import location_to_encoded_filename


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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.reflist = []  # type: List[str]

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


def plugin_loaded() -> None:
    register_plugin(EclipseJavaDevelopmentTools)


def plugin_unloaded() -> None:
    unregister_plugin(EclipseJavaDevelopmentTools)
