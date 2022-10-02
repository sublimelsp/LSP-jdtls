# Handler for workspace/executeClientCommand requests.
# See https://github.com/microsoft/vscode-java-test/tree/main/src/commands

# execute_client_command is called in m_workspace_executeClientCommand in plugin.py

import sublime

from LSP.plugin import Response, Session
from LSP.plugin.core.types import Any, Callable, Optional, List

from .constants import SESSION_NAME
from .quick_select_panel import QuickSelect, SelectableItem


def execute_client_command(session: Session, request_id, command, arguments):
    # There should be an entry for every JavaTestRunnerCommand
    # found in https://github.com/microsoft/vscode-java-test/blob/main/src/constants.ts
    client_command_handler = {
        "_java.test.askClientForChoice": _ask_client_for_choice,
        "_java.test.askClientForInput": _ask_client_for_input
    }

    if command in client_command_handler:
        def send_response(params):
            session.send_response(Response(request_id, params))

        client_command_handler[command](session, send_response, *arguments)
    else:
        raise ValueError("{}: no command handler for client command {}. Open an issue on sublimelsp/LSP-jdtls".format(SESSION_NAME, command))


# HANDLERS
###############################


def _ask_client_for_choice(session: Session, response_callback: Callable[[Any], None], placeholder: str, items, multi_select: bool):
    def on_selection_done(selection: Optional[List[SelectableItem]]):
        if not selection:
            response_callback(None)
        else:
            if multi_select:
                response_callback([x.value or x.label for x in selection])
            else:
                response_callback(selection[0].value or selection[0].label)

    # items = [sublime.QuickPanelItem(x["label"], x["description"] if "description" in x else "") for x in items]
    items = [SelectableItem(x["label"], x.get("value", None), x.get("detail", ""), x.get("description", ""), x.get("picked", False)) for x in items]
    QuickSelect(None, items, placeholder=placeholder, multi_select=multi_select).show().then(on_selection_done)
    # sublime.active_window().show_quick_panel(panel_items, on_select, sublime.KEEP_OPEN_ON_FOCUS_LOST, placeholder=placeholder)


def _ask_client_for_input(session: Session, response_callback: Callable[[Any], None], caption: str, initial_text: str):
    def on_done(answer: str):
        response_callback(answer)

    def on_cancel():
        response_callback(None)

    sublime.active_window().show_input_panel(caption, initial_text, on_done, None, on_cancel)
