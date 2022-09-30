# Handler for workspace/executeClientCommand requests.
# See https://github.com/microsoft/vscode-java-test/tree/main/src/commands

# execute_client_command is called in m_workspace_executeClientCommand in plugin.py

import sublime

from LSP.plugin import Response, Session
from LSP.plugin.core.types import Any, Callable

from .constants import SESSION_NAME


def execute_client_command(session: Session, request_id, command, arguments):
    # There should be an entry for every JavaTestRunnerCommand
    # found in https://github.com/microsoft/vscode-java-test/blob/main/src/constants.ts
    client_command_handler = {
        "_java.test.askClientForChoice": _ask_client_for_choice
    }

    if command in client_command_handler:
        def send_response(params):
            session.send_response(Response(request_id, params))

        client_command_handler[command](session, send_response, *arguments)
    else:
        print("{}: no command handler for client command {}".format(SESSION_NAME, command))


# HANDLERS
###############################


def _ask_client_for_choice(session: Session, response_callback: Callable[[Any], None], placeholder: str, items, multi_select: bool):
    def on_select(index):
        if index == -1:
            response_callback(None)
        else:
            response_params = items[index]["value"] if "value" in items[index] else items[index]["label"]
            # Multiselect is currently unsupported by sublime, fallback to single select.
            if multi_select:
                response_params = [response_params]
            response_callback(response_params)

    panel_items = [sublime.QuickPanelItem(x["label"], x["description"] if "description" in x else "") for x in items]
    sublime.active_window().show_quick_panel(panel_items, on_select, sublime.KEEP_OPEN_ON_FOCUS_LOST, placeholder=placeholder)
