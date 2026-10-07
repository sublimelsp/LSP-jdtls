""" Handler for workspace/executeClientCommand requests. """

# See https://github.com/microsoft/vscode-java-test/tree/main/src/commands
# See https://github.com/redhat-developer/vscode-java/blob/master/src/commands.ts

from __future__ import annotations

from typing import Any

from LSP.plugin import Promise
from LSP.protocol import ExecuteCommandParams

from .quick_input_panel import QuickSelect, QuickTextInput, SelectableItem


def workspace_executeClientCommand(params: ExecuteCommandParams) -> Promise[Any]:
    command = params["command"]
    arguments: list[Any] = params.get("arguments") or []

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
        return client_command_requests[command](*arguments)
    return Promise.resolve(None)


# HANDLERS
###############################


# vscode-java EXTENSION


def _reload_bundles() -> Promise[list[str]]:
    return Promise.resolve([])  # we do include all extensions from the start


# vscode-java-test EXTENSION


def _ask_client_for_choice(placeholder: str, items: list[Any], multi_select: bool) -> Promise[Any]:

    def on_selection_done(selection: list[SelectableItem] | None) -> Any:
        if not selection:
            return None
        if multi_select:
            return [x.value or x.label for x in selection]
        return selection[0].value or selection[0].label

    preselect_index = 0
    for i, item in enumerate(items):
        if item.get("picked", False):
            preselect_index = i

    qs_items = [
        SelectableItem(
            x["label"],
            x.get("value", None),
            x.get("detail", ""),
            x.get("description", ""),
        )
        for x in items
    ]
    return QuickSelect(
        None,
        qs_items,
        preselect_index=preselect_index,
        placeholder=placeholder,
        multi_select=multi_select,
    ).show().then(on_selection_done)


def _ask_client_for_input(caption: str, initial_text: str) -> Promise[str | None]:
    return QuickTextInput(None, caption, initial_text).show()
