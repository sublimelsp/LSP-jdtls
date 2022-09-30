# Handler for workspace/executeClientCommand maching
# https://github.com/microsoft/vscode-java-test/tree/main/src/commands

# Every command handler must be registered in m_workspace_executeClientCommand in plugin.py


from LSP.plugin import Response, Session
from LSP.plugin.core.types import Any, Callable


SESSION_NAME = "jdtls"


def _ask_client_for_choice(session: Session, response_callback: Callable[[Any], None], *arguments):
    pass


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
