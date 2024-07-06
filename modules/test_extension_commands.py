import json
import os

import sublime
from LSP.plugin import Session, parse_uri, uri_from_view
from LSP.plugin.core.constants import KIND_CLASS, KIND_METHOD
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.protocol import (
    ExecuteCommandParams,  # noqa: F401
    WorkspaceEdit,
)
from LSP.plugin.core.typing import Callable, List, Tuple
from LSP.plugin.core.views import (
    first_selection_region,
    offset_to_point,
)

from .constants import SESSION_NAME
from .installer import vscode_plugin_path
from .quick_input_panel import QuickSelect, SelectableItem
from .test_extension_server import JunitResultsServer, TestNgResultsServer
from .text_extension_protocol import (
    IJavaTestItem,
    IJUnitLaunchArguments,
    ITestNavigationResult,
    TestKind,
    TestLevel,
)
from .utils import (
    LspJdtlsTextCommand,
    flatten_test_items,
    open_and_focus_uri,
    sublime_debugger_available,
)


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

            sublime.set_timeout_async(
                lambda: session.apply_workspace_edit_async(workspace_edit).then(
                    open_changed_file
                )
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


class LspJdtlsTestCommand(LspJdtlsTextCommand):
    """
    Debug the test class in the current view.
    """

    def run_jdtls_command(self, edit, session: Session):
        if not sublime_debugger_available():
            sublime.error_message(
                "Sublime Debugger must be installed and activated to use this command!"
            )
            raise ValueError()

        command = {
            "command": "vscode.java.test.findTestTypesAndMethods",
            "arguments": [uri_from_view(self.view)],
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(
            lambda result: print("Error fetching tests: " + str(result))
            if isinstance(result, Exception)
            else self.select_test_item(result or [], self.fetch_debug_args)
        )

    def select_test_item(
        self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]
    ) -> None:
        ...

    def fetch_debug_args(self, test_item: IJavaTestItem):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        command = {
            "command": "vscode.java.test.junit.argument",
            "arguments": [
                json.dumps(
                    {
                        "projectName": test_item["projectName"],
                        "testLevel": test_item["testLevel"],
                        "testKind": test_item["testKind"],
                        "testNames": [self.get_test_name(test_item)],
                    }
                )
            ],
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(
            lambda result: print("Error fetching debug arguments: " + str(result))
            if isinstance(result, Exception)
            else self.resolve_debug_classpath(test_item, result["body"])
        )

    def get_test_name(self, test_item: IJavaTestItem) -> str:
        if test_item["testKind"] == TestKind.TestNG:
            return test_item["fullName"]
        elif test_item["testLevel"] == TestLevel.Class:
            return test_item["fullName"]
        else:
            return test_item["jdtHandler"]

    def resolve_debug_classpath(
        self, test_item: IJavaTestItem, launch_args: IJUnitLaunchArguments
    ):
        session = self.session_by_name(SESSION_NAME)
        if not session:
            return
        command = {
            "command": "java.project.getClasspaths",
            "arguments": [uri_from_view(self.view), json.dumps({"scope": "test"})],
        }  # type: ExecuteCommandParams

        def merge_classpaths(classpath: List[str]):
            launch_args["classpath"].extend(
                x for x in classpath if x not in launch_args["classpath"]
            )
            self.launch(test_item, launch_args)

        session.execute_command(command, False).then(
            lambda result: print("Error resolving classpath: " + str(result))
            if isinstance(result, Exception)
            else merge_classpaths(result["classpaths"])
        )

    def launch(self, test_item: IJavaTestItem, launch_args: IJUnitLaunchArguments):
        """
        See resolveLaunchConfigurationForRunner
        """

        debugger_config = {
            "name": test_item["label"],
            "type": "java",
            "request": "launch",
            "projectName": launch_args["projectName"],
            "cwd": launch_args["workingDirectory"],
            "classPaths": launch_args["classpath"],
            "modulePaths": launch_args["modulepath"],
            "vmArgs": " ".join(launch_args["vmArguments"]),
            "noDebug": False,
        }

        if (
            test_item["testKind"] == TestKind.JUnit5
            or test_item["testKind"] == TestKind.JUnit
        ):
            server = JunitResultsServer()

            # The port in launch_args is a placeholder. (See vscode-java-test)
            port_idx = launch_args["programArguments"].index("-port") + 1
            launch_args["programArguments"][port_idx] = str(server.get_port())

            debugger_config["args"] = " ".join(launch_args["programArguments"])
            debugger_config["mainClass"] = launch_args["mainClass"]

        elif test_item["testKind"] == TestKind.TestNG:
            server = TestNgResultsServer()

            jarpath = os.path.join(
                vscode_plugin_path("vscode-java-test"),
                "extension/server/com.microsoft.java.test.runner-jar-with-dependencies.jar",
            )

            debugger_config["mainClass"] = "com.microsoft.java.test.runner.Launcher"
            debugger_config["classPaths"] += [jarpath]
            debugger_config["args"] = " ".join(self.get_test_ng_args(test_item, server))

        else:
            raise ValueError(
                "TestKind " + str(test_item["testKind"]) + " not supported"
            )

        server.receive_test_results_async()
        window = self.view.window()
        if window:
            window.run_command(
                "debugger",
                {"action": "open_and_start", "configuration": debugger_config},
            )

    def get_test_ng_args(
        self, test_item: IJavaTestItem, server: TestNgResultsServer
    ) -> List[str]:
        args = [str(server.get_port()), "testng"]

        flattened = flatten_test_items([test_item])
        for test in flattened:
            if test["testLevel"] == TestLevel.Method:
                # id has pattern <project>@<class>#<method>
                split = test["id"].split("@")
                if len(split) == 2:
                    args.append(split[1])
        return args


class LspJdtlsRunTestClass(LspJdtlsTestCommand):
    """
    Debug the test class in the current view.
    """

    def select_test_item(
        self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]
    ) -> None:
        for item in test_items or []:
            if item["testLevel"] == TestLevel.Class:
                then(item)
                return

        window = self.view.window()
        if window and window.is_valid():
            window.status_message("No test class found")


class LspJdtlsRunTestAtCursor(LspJdtlsTestCommand):
    """
    Debug the nearest test method in the current view.
    """

    def select_test_item(
        self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]
    ) -> None:
        if not test_items:
            window = self.view.window()
            if window and window.is_valid():
                window.status_message("No test method found at cursor")
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
                    if (
                        item is None
                        or test["range"]["start"]["line"]
                        > item["range"]["start"]["line"]
                    ):  # item["range"] cannot be None
                        item = test

        if item:
            then(item)


class LspJdtlsRunTest(LspJdtlsTestCommand):
    """
    Debug the a test method from current view.
    """

    def select_test_item(
        self, test_items: List[IJavaTestItem], then: Callable[[IJavaTestItem], None]
    ) -> None:
        if not test_items:
            window = self.view.window()
            if window and window.is_valid():
                window.status_message("No test method found")
            return

        def kind_from_test_level(test_level: TestLevel) -> Tuple[int, str, str]:
            if test_level == TestLevel.Class:
                return KIND_CLASS
            elif test_level == TestLevel.Method:
                return KIND_METHOD
            else:
                return sublime.KIND_AMBIGUOUS

        tests = flatten_test_items(test_items)
        items = [
            SelectableItem(
                lens["fullName"],
                i,
                lens["label"],
                kind=kind_from_test_level(lens["testLevel"]),
            )
            for i, lens in enumerate(tests)
        ]
        QuickSelect(None, items).show().then(
            lambda x: then(tests[x[0].value]) if x else None
        )
