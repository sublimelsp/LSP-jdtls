import sublime

from LSP.plugin import LspTextCommand, Session, parse_uri
from LSP.plugin.core.typing import List

from .constants import SESSION_NAME
from .text_extension_protocol import IJavaTestItem


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


class LspJdtlsTextCommand(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit, **args):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        self.run_jdtls_command(edit, session, **args)

    def run_jdtls_command(self, edit, session: Session, **args):
        ...
