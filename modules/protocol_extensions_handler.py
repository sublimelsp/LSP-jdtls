"""
Handler for JDTLS protocol extensions.

See https://github.com/redhat-developer/vscode-java/blob/master/src/standardLanguageClient.ts
"""
import sublime
from LSP.plugin import Session
from LSP.plugin.core.protocol import (
    Command,
    ExecuteCommandParams,  # noqa: F401
)
from LSP.plugin.core.typing import Optional

from .protocol import ActionableNotification, ProgressReport, StatusReport
from .quick_input_panel import QuickSelect, SelectableItem


def language_actionableNotification(
    session: Session, notification: ActionableNotification
):
    def run_command(command: Optional[Command]):
        if not command:
            return
        params = {"command": command["command"]}  # type: ExecuteCommandParams
        if "arguments" in command:
            params["arguments"] = command["arguments"]
        session.execute_command(params, False)

    command = None  # type: Optional[Command]
    if "commands" not in notification or len(notification["commands"]) == 0:
        sublime.message_dialog(notification["message"])
    elif len(notification["commands"]) == 1:
        if sublime.ok_cancel_dialog(
            notification["message"], notification["commands"][0]["title"]
        ):
            command = notification["commands"][0]
    elif len(notification["commands"]) == 2:
        c_yes, c_no = notification["commands"]
        selected = sublime.yes_no_cancel_dialog(
            notification["message"], c_yes["title"], c_no["title"]
        )
        if selected == sublime.DIALOG_YES:
            command = c_yes
        elif selected == sublime.DIALOG_NO:
            command = c_no
    else:
        items = [SelectableItem(c["title"], c) for c in notification["commands"]]
        QuickSelect(session.window, items, 0, notification["message"]).show().then(
            lambda x: run_command(x[0].value) if x else None
        )

    run_command(command)


progress_reports = dict()  # type: dict[str, str]


def language_progressReport(session: Session, params: ProgressReport):
    key = params["id"] if "id" in params else "jdtls-status-dummy-key"
    progress_reports[key] = "{}% {}".format(params["workDone"] / params["totalWork"] * 100, params["task"])
    _update_config_status_async(session)
    if params["complete"]:
        progress_reports.pop(key, None)
        sublime.set_timeout_async(lambda: _update_config_status_async(session), 1000)


def _update_config_status_async(session: Session) -> None:
    session.set_config_status_async(", ".join(progress_reports.values()))


def language_status(session: Session, params: StatusReport) -> None:
    message = params.get("message")
    if not message:
        return
    session.window.status_message(message)
