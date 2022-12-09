from .constants import SESSION_NAME, SETTINGS_FILENAME
from .text_extension_protocol import IJavaTestItem

from LSP.plugin import AbstractPlugin, LspTextCommand, Session, parse_uri
from LSP.plugin.core.typing import List, Any, Callable, Optional

import sublime


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


def add_notification_handler(notification: str, handler: Callable[[Session, Any], None]):
    """
    Adds a handler for a notification.
    The handler must accept a Session and the notification parameters.
    """
    def decorator(cls):
        def handle(self: AbstractPlugin, params: Any):
            session = self.weaksession()
            if not session:
                return
            handler(session, params)
        setattr(cls, "m_" + notification.replace("/", "_"), handle)
        return cls
    return decorator


def add_request_handler(request: str, handler: Callable[[Session, Any, int], None]):
    """
    Adds a handler for a request.
    The handler must accept a Session, the notification parameters and the request id.
    """
    def decorator(cls):
        def handle(self: AbstractPlugin, params: Any, request_id: int):
            session = self.weaksession()
            if not session:
                return
            handler(session, params, request_id)
        setattr(cls, "m_" + request.replace("/", "_"), handle)
        return cls
    return decorator


def view_for_uri_async(session: Session, uri: Optional[str]) -> Optional[sublime.View]:
    """ Returns a view matching the uri that is attached to the given session.
    Only safe to use in the async thread.
    """
    for view_protocol in session.session_views_async():
        if view_protocol.get_uri() == uri:
            return view_protocol.view
    return None


class LspJdtlsTextCommand(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit, **args):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        self.run_jdtls_command(edit, session, **args)

    def run_jdtls_command(self, edit, session: Session, **args):
        ...
