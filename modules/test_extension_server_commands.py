import sublime

from LSP.plugin import Session, parse_uri
from LSP.plugin.core.edit import WorkspaceEdit, parse_workspace_edit
from LSP.plugin.core.protocol import ExecuteCommandParams
from LSP.plugin.core.views import KIND_CLASS, KIND_METHOD, offset_to_point, uri_from_view, first_selection_region
from LSP.plugin.core.typing import List, Tuple, Callable

from .quick_input_panel import QuickSelect, SelectableItem
from .text_extension_protocol import ITestNavigationResult, IJavaTestItem, TestLevel
from .utils import flatten_test_items, sublime_debugger_available, LspJdtlsTextCommand, open_and_focus_uri


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


def run_test_item(test_item: IJavaTestItem):
    print(test_item)


class LspJdtlsTestCommand(LspJdtlsTextCommand):
    """
    Debug the test class in the current view.
    """

    def run_jdtls_command(self, edit, session: Session):
        if not sublime_debugger_available():
            sublime.error_message("Sublime Debugger must be installed and activated to use this command!")
            raise ValueError()

        commands = session.capabilities.get("executeCommandProvider.commands")
        if "vscode.java.test.search.codelens" in commands:
            resolve_command = "vscode.java.test.search.codelens"
        elif "vscode.java.test.findTestTypesAndMethods" in commands:
            resolve_command = "vscode.java.test.findTestTypesAndMethods"
        else:
            sublime.error_message("JDTLS test extension not found.")
            raise ValueError("JDTLS test extension not found.")
        command = {
            "command": resolve_command,
            # file_uri, (True: Goto test, False: Goto implementation)
            "arguments": [uri_from_view(self.view)],
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(
            lambda result: self._on_error(result)
            if isinstance(result, Exception)
            else self._on_success(result)
        )

    def _on_success(
        self, test_items: List[IJavaTestItem]
    ):
        self.select_test_item(test_items, run_test_item)

    def _on_error(self, error):
        print("Error fetching tests: " + error)

    def select_test_item(self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]) -> None:
        ...


class LspJdtlsRunTestClass(LspJdtlsTestCommand):
    """
    Debug the test class in the current view.
    """

    def select_test_item(self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]) -> None:
        for lens in test_items:
            if lens["testLevel"] == TestLevel.Class:
                then(lens)
                return
        sublime.error_message("No test at class level found")
        raise ValueError("No test at class level found")


class LspJdtlsRunTestAtCursor(LspJdtlsTestCommand):
    """
    Debug the nearest test method in the current view.
    """

    def select_test_item(self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]) -> None:
        if not test_items:
            return
        item = None
        flattened = flatten_test_items(test_items)
        region = first_selection_region(self.view)
        if region is None:
            return
        cursor_line = offset_to_point(self.view, region.b).row

        for test in flattened:
            if test["testLevel"] == TestLevel.Method:
                if test["range"] and test["range"]["start"]["line"] <= cursor_line:
                    if item is None or test["range"]["start"]["line"] > item["range"]["start"]["line"]:  # item["range"] cannot be None
                        item = test

        if item:
            then(item)


class LspJdtlsRunTest(LspJdtlsTestCommand):
    """
    Debug the a test method from current view.
    """

    def select_test_item(self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]) -> None:
        def kind_from_test_level(test_level: TestLevel) -> Tuple[int, str, str]:
            if test_level == TestLevel.Class:
                return KIND_CLASS
            elif test_level == TestLevel.Method:
                return KIND_METHOD
            else:
                return sublime.KIND_AMBIGUOUS

        tests = flatten_test_items(test_items)
        items = [SelectableItem(lens["fullName"], i, lens["label"], kind=kind_from_test_level(lens["testLevel"])) for i, lens in enumerate(tests)]
        QuickSelect(None, items).show().then(lambda x: then(tests[x[0].value]) if x else None)
