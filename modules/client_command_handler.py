# Handler for workspace/executeClientCommand requests.

# See https://github.com/microsoft/vscode-java-test/tree/main/src/commands
# See https://github.com/redhat-developer/vscode-java/blob/master/src/commands.ts

# execute_client_command is called in m_workspace_executeClientCommand in plugin.py

import sublime

from LSP.plugin import Response, Session
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.types import Any, Callable, Optional, List, Dict
from LSP.plugin.core.views import location_to_encoded_filename
from .utils import set_lsp_project_setting
from .protocol import FeatureStatus

from .constants import SETTING_ENABLE_NULL_ANALYSIS
from .quick_input_panel import QuickSelect, SelectableItem, QuickTextInput


def handle_client_command_request(session: Session, request_id, command, arguments) -> bool:
    """
    Returns true if the command was handled.
    """
    client_command_requests = {
        # vscode-java EXTENSION
        "_java.reloadBundles.command": _reload_bundles,
        # vscode-java-test EXTENSION
        # There should be an entry for every JavaTestRunnerCommand
        # found in https://github.com/microsoft/vscode-java-test/blob/main/src/constants.ts
        "_java.test.askClientForChoice": _ask_client_for_choice,
        "_java.test.askClientForInput": _ask_client_for_input,
    }

    if command in client_command_requests:
        def send_response(params):
            session.send_response(Response(request_id, params))

        client_command_requests[command](session, send_response, *arguments)
        return True
    return False


def handle_client_command(session: Session, done: Callable[[], None], command, arguments):
    """
    Returns true if the command was handled.
    """
    client_commands = {
        "java.compile.nullAnalysis.setMode": _set_null_analysis_mode,
        "java.apply.workspaceEdit": _apply_workspace_edit,
        "java.show.references": _show_references,
    }
    if command in client_commands:
        client_commands[command](session, done, *arguments)
        return True
    return False


# HANDLERS
###############################


## vscode-java EXTENSION

def _reload_bundles(session: Session, response_callback: Callable[[Any], None]):
    pass


## vscode-java-test EXTENSION

def _ask_client_for_choice(session: Session, response_callback: Callable[[Any], None], placeholder: str, items, multi_select: bool):
    def on_selection_done(selection: Optional[List[SelectableItem]]):
        if not selection:
            response_callback(None)
        else:
            if multi_select:
                response_callback([x.value or x.label for x in selection])
            else:
                response_callback(selection[0].value or selection[0].label)

    preselect_index = 0
    for i, item in enumerate(items):
        if item.get("picked", False):
            preselect_index = i

    qs_items = [SelectableItem(x["label"], x.get("value", None), x.get("detail", ""), x.get("description", "")) for x in items]
    QuickSelect(None, qs_items, preselect_index=preselect_index, placeholder=placeholder, multi_select=multi_select).show().then(on_selection_done)


def _set_null_analysis_mode(session: Session, done: Callable[[], None], status: FeatureStatus):
    mode = "automatic" if status == FeatureStatus.automatic else "disabled"
    set_lsp_project_setting(session.window, SETTING_ENABLE_NULL_ANALYSIS, mode)
    sublime.set_timeout_async(done)


def _ask_client_for_input(session: Session, response_callback: Callable[[Any], None], caption: str, initial_text: str):
    def on_done(answer: Optional[str]):
        response_callback(answer)

    QuickTextInput(None, caption, initial_text).show().then(on_done)


def _apply_workspace_edit(session: Session, done: Callable[[], None], *arguments):
    changes = parse_workspace_edit(arguments[0])
    window = session.window
    sublime.set_timeout(
        lambda: apply_workspace_edit(window, changes).then(
            lambda _: sublime.set_timeout_async(done)
        )
    )


def _show_references(session: Session, done: Callable[[], None], *arguments):
    reflist = []

    def _open_ref_index(index: int, transient: bool = False) -> None:
        if index != -1:
            flags = (
                sublime.ENCODED_POSITION | sublime.TRANSIENT
                if transient
                else sublime.ENCODED_POSITION
            )
            session.window.open_file(reflist[index], flags)

    def _on_ref_choice(index: int) -> None:
        _open_ref_index(index, transient=False)

    def _on_ref_highlight(index: int) -> None:
        _open_ref_index(index, transient=True)

    reflist = [location_to_encoded_filename(r) for r in arguments[2]]  # type: ignore
    session.window.show_quick_panel(
        reflist,
        _on_ref_choice,
        sublime.KEEP_OPEN_ON_FOCUS_LOST,
        0,
        _on_ref_highlight,
    )

    done()
