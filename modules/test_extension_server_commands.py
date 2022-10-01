
from LSP.plugin import LspTextCommand
from LSP.plugin.core.edit import WorkspaceEdit, parse_workspace_edit
from LSP.plugin.core.open import open_file
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.views import uri_from_view, first_selection_region

from .constants import SESSION_NAME


class LspJdtlsGenerateTests(LspTextCommand):

    session_name = SESSION_NAME

    def run(self, edit):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        region = first_selection_region(self.view)
        if region is None:
            return

        command = {
            "command": "vscode.java.test.generateTests",
            # file_uri, offset
            "arguments": [uri_from_view(self.view), region.b]
        }  # type: ExecuteCommandParams

        def _on_success(workspace_edit: WorkspaceEdit):
            parsed_worspace_edit = parse_workspace_edit(workspace_edit)

            def open_changed_file(result):
                window = self.view.window()
                if window and parsed_worspace_edit:
                    for uri in parsed_worspace_edit:
                        open_file(window, uri).then(lambda view: window.focus_view(view) if view else None)
                        return

            session.apply_parsed_workspace_edits(parsed_worspace_edit).then(open_changed_file)

        session.execute_command(command, False).then(_on_success)
