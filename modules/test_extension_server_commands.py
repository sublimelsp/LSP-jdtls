from LSP.plugin import Session
from LSP.plugin.core.edit import WorkspaceEdit, parse_workspace_edit
from LSP.plugin.core.open import open_file
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.views import uri_from_view, first_selection_region

from .utils import LspJdtlsTextCommand


class LspJdtlsGenerateTests(LspJdtlsTextCommand):

    def run_jdtls_command(self, edit, session: Session):
        region = first_selection_region(self.view)
        if region is None:
            return

        command = {
            "command": "vscode.java.test.generateTests",
            # file_uri, offset
            "arguments": [uri_from_view(self.view), region.b]
        }  # type: ExecuteCommandParams

        def _on_done(workspace_edit: WorkspaceEdit):
            if workspace_edit is None:
                return

            if isinstance(workspace_edit, Exception):
                print(workspace_edit)
                return

            parsed_worspace_edit = parse_workspace_edit(workspace_edit)

            def open_changed_file(result):
                window = self.view.window()
                if window and parsed_worspace_edit:
                    for uri in parsed_worspace_edit:
                        open_file(window, uri).then(lambda view: window.focus_view(view) if view else None)
                        return

            session.apply_parsed_workspace_edits(parsed_worspace_edit).then(open_changed_file)

        session.execute_command(command, False).then(_on_done)


class LspJdtlsGotoTest(LspJdtlsTextCommand):
    """
    Command to switch to tests and implementation.
    """

    def run_jdtls_command(self, edit, session: Session, goto_test_or_implementation: bool):
        command = {
            "command": "vscode.java.test.navigateToTestOrTarget",
            # file_uri, (True: Goto test, False: Goto implementation)
            "arguments": [uri_from_view(self.view), goto_test_or_implementation]
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(print)

