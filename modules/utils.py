import sublime

from LSP.plugin import LspTextCommand, Session, parse_uri

from .constants import SESSION_NAME


def open_and_focus_uri(window: sublime.Window, uri: str):
    # Replace that with session.open_uri_async once that does also focus an open view.
    _, file_name = parse_uri(uri)
    window.open_file(file_name)


class LspJdtlsTextCommand(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit, **args):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        self.run_jdtls_command(edit, session, **args)

    def run_jdtls_command(self, edit, session: Session, **args):
        ...
