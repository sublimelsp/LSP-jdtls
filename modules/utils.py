import sublime

from LSP.plugin import LspTextCommand, Session, parse_uri
from LSP.plugin.core.typing import List, Any

from .constants import SESSION_NAME, SETTINGS_FILENAME
from .text_extension_protocol import IJavaTestItem


def set_lsp_project_setting(window: sublime.Window, setting: str, value: Any):
    if not window.project_file_name():
        sublime.message_dialog("A sublime-project is required to save project settings.")
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
    sublime.set_timeout(lambda: print(window.project_data), 100)


def get_settings() -> sublime.Settings:
    return sublime.load_settings(SETTINGS_FILENAME)


def sublime_debugger_available() -> bool:
    return "Packages/Debugger/debugger.sublime-settings" in sublime.find_resources(
        "debugger.sublime-settings"
    )


def open_and_focus_uri(window: sublime.Window, uri: str):
    # Replace that with session.open_uri_async once that does also focus an open view.
    _, file_name = parse_uri(uri)
    window.open_file(file_name)


def flatten_test_items(test_items: List[IJavaTestItem]) -> List[IJavaTestItem]:
    test_list = []
    for item in test_items:
        test_list.append(item)
        if "children" in item:
            test_list += flatten_test_items(item["children"])
    return test_list


def filter_lines(string: str, patterns: List[str]):
    return "".join(line for line in string.splitlines(True) if not [p for p in patterns if p in line])


class LspJdtlsTextCommand(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit, **args):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        self.run_jdtls_command(edit, session, **args)

    def run_jdtls_command(self, edit, session: Session, **args):
        ...
