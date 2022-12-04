"""
Handler for JDTLS protocol extensions.

See https://github.com/redhat-developer/vscode-java/blob/master/src/standardLanguageClient.ts
"""
import sublime
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.protocol import Command, ExecuteCommandParams
from LSP.plugin.core.typing import Optional

from .protocol import ActionableNotification
from .quick_input_panel import QuickSelect, SelectableItem


def handle_actionable_notification(
    session: Session, notification: ActionableNotification
):

    def run_command(command: Optional[Command]):
        if not command:
            return
        params = {
            "command": command["command"]
        }  # type: ExecuteCommandParams
        if "arguments" in command:
            params["arguments"] = command["arguments"]
        session.execute_command(params, False)

    command = None  # type: Optional[Command]
    if "commands" not in notification or len(notification["commands"]) == 0:
        sublime.message_dialog(notification["message"])
    elif len(notification["commands"]) == 1:
        if sublime.ok_cancel_dialog(notification["message"], notification["commands"][0]["title"]):
            command = notification["commands"][0]
    elif len(notification["commands"]) == 2:
        c_yes, c_no = notification["commands"]
        selected = sublime.yes_no_cancel_dialog(notification["message"], c_yes["title"], c_no["title"])
        if selected == sublime.DIALOG_YES:
            command = c_yes
        elif selected == sublime.DIALOG_NO:
            command = c_no
    else:
        items = [SelectableItem(c["title"], c) for c in notification["commands"]]
        QuickSelect(session.window, items, 0, notification["message"]).show().then(lambda x: run_command(x[0].value) if x else None)

    run_command(command)
