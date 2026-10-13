from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sublime
from LSP.plugin import LspTextCommand, Session, parse_uri
from typing_extensions import override

from .constants import SESSION_NAME, SETTINGS_FILENAME

if TYPE_CHECKING:
    from .text_extension_protocol import IJavaTestItem


def set_lsp_project_setting(window: sublime.Window, setting: str, value: Any) -> None:
    if not window.project_file_name():
        sublime.message_dialog(
            "A sublime-project is required to save project settings."
        )
        window.run_command("save_project_and_workspace_as")

    project_data = window.project_data() or {}
    project_keys = ["settings", "LSP", SESSION_NAME, "settings"]

    current = project_data
    for project_key in project_keys:
        subkey = current.get(project_key, {})
        current[project_key] = subkey
        current = subkey

    current[setting] = value

    sublime.set_timeout(lambda: window.set_project_data(project_data))


def get_settings() -> sublime.Settings:
    return sublime.load_settings(SETTINGS_FILENAME)


def sublime_debugger_available() -> bool:
    settings_names = ["debugger.sublime-settings", "Debugger.sublime-settings"]
    return any(any(file.endswith(name) for file in sublime.find_resources(name)) for name in settings_names)


def open_and_focus_uri(window: sublime.Window, uri: str) -> None:
    # Replace that with session.open_uri_async once that does also focus an open view.
    _, file_name = parse_uri(uri)
    window.open_file(file_name)


def flatten_test_items(test_items: list[IJavaTestItem]) -> list[IJavaTestItem]:
    test_list = []
    for item in test_items:
        test_list.append(item)
        if "children" in item:
            test_list += flatten_test_items(item["children"])
    return test_list


def filter_lines(string: str, patterns: list[str]) -> str:
    return "".join(
        line
        for line in string.splitlines(True)
        if not [p for p in patterns if p in line]
    )


def view_for_uri_async(session: Session, uri: str | None) -> sublime.View | None:
    """Returns a view matching the uri that is attached to the given session.
    Only safe to use in the async thread.
    """
    for view_protocol in session.session_views_async():
        if view_protocol.get_uri() == uri:
            return view_protocol.view
    return None


class LspJdtlsTextCommand(LspTextCommand):
    @override
    def run(self, edit, **args) -> None:
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        self.run_jdtls_command(edit, session, **args)

    def run_jdtls_command(self, edit, session: Session, **args) -> None:
        ...
