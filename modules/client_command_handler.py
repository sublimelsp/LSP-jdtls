# Handler for workspace/executeClientCommand requests.

# See https://github.com/microsoft/vscode-java-test/tree/main/src/commands
# See https://github.com/redhat-developer/vscode-java/blob/master/src/commands.ts

# execute_client_command is called in m_workspace_executeClientCommand in plugin.py

from LSP.plugin import Response, Session
from LSP.plugin.core.types import Any, Callable, Optional, List

from .constants import SESSION_NAME
from .quick_input_panel import QuickSelect, SelectableItem, QuickTextInput


def execute_client_command(session: Session, request_id, command, arguments):
    client_command_handler = {
        # vscode-java EXTENSION
        "_java.reloadBundles.command": _reload_bundles,
        # vscode-java-test EXTENSION
        # There should be an entry for every JavaTestRunnerCommand
        # found in https://github.com/microsoft/vscode-java-test/blob/main/src/constants.ts
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


def _ask_client_for_input(session: Session, response_callback: Callable[[Any], None], caption: str, initial_text: str):
    def on_done(answer: Optional[str]):
        response_callback(answer)

    QuickTextInput(None, caption, initial_text).show().then(on_done)
