import sublime

from LSP.plugin import Session, parse_uri
from LSP.plugin.core.edit import WorkspaceEdit, parse_workspace_edit
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.views import KIND_CLASS, uri_from_view, first_selection_region

from .quick_input_panel import QuickSelect, SelectableItem
from .text_extension_protocol import ITestNavigationResult
from .utils import LspJdtlsTextCommand, open_and_focus_uri


class LspJdtlsGenerateTests(LspJdtlsTextCommand):
    def run_jdtls_command(self, edit, session: Session):
        region = first_selection_region(self.view)
        if region is None:
            return

        command = {
            "command": "vscode.java.test.generateTests",
            # file_uri, offset
            "arguments": [uri_from_view(self.view), region.b],
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
                        open_and_focus_uri(window, uri)
                        return

            session.apply_parsed_workspace_edits(parsed_worspace_edit).then(
                open_changed_file
            )

        session.execute_command(command, False).then(_on_done)


class LspJdtlsGotoTest(LspJdtlsTextCommand):
    """
    Command to switch to tests and implementation.
    """

    def run_jdtls_command(
        self, edit, session: Session, goto_test_or_implementation: bool
    ):
        command = {
            "command": "vscode.java.test.navigateToTestOrTarget",
            # file_uri, (True: Goto test, False: Goto implementation)
            "arguments": [uri_from_view(self.view), goto_test_or_implementation],
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(
            lambda result: self._on_error(result)
            if isinstance(result, Exception)
            else self._on_success(result, goto_test_or_implementation)
        )

    def _on_success(
        self, result: ITestNavigationResult, goto_test_or_implementation: bool
    ):
        items = result["items"]
        test_or_impl = (
            "test class" if goto_test_or_implementation else "implementation class"
        )

        if not items:
            _, file_path = parse_uri(result["location"]["uri"])
            sublime.status_message("No {} found for {}".format(test_or_impl, file_path))
        elif len(items) == 1:
            window = self.view.window() or sublime.active_window()
            open_and_focus_uri(window, items[0]["uri"])
        else:
            window = self.view.window() or sublime.active_window()
            selectable_items = [
                SelectableItem(
                    item["simpleName"],
                    item["uri"],
                    item["fullyQualifiedName"],
                    kind=KIND_CLASS,
                )
                for item in items
            ]

            def _on_seleceted(selection):
                if selection:
                    open_and_focus_uri(window, selection[0].value)

            QuickSelect(
                window, selectable_items, placeholder="Select {}".format(test_or_impl)
            ).show().then(_on_seleceted)

    def _on_error(self, error):
        print(error)
