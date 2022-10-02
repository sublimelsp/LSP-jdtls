"""
Implements an high level API to query a selection from an user.

Since Quick Panels only support support single selection, ListInputHandler and a dummy command is used.

Usage:
context = QuickSelect(...).show().then( do_something_with_selection )

Inspired by https://github.com/daveleroy/sublime_debugger/blob/master/modules/ui/input.py
"""

import sublime
import sublime_plugin

from LSP.plugin.core.promise import Promise
from LSP.plugin.core.typing import List, Optional, Dict, Any, Callable, Tuple


class SelectableItem:
    def __init__(
        self,
        label: str,
        value: Any,
        details: str = "",
        annotation: str = "",
        kind: Tuple[int, str, str] = sublime.KIND_AMBIGUOUS,
        on_select_confirmed: Callable[[], None] = lambda: None,
    ):
        """
        Constructs a new instance.

        :param      label:      The label that is mached agains the input
        :param      value:      The value that is returned when the selection is done
        :param      details:    The details show below the item
        :param      annotation: The annotation shown to the right of the item
        :param      kind_id:    The kind identifier, controls the icon
        :param      on_select_confirmed: Called when the item was selected and the panel is confirmed
        """
        self.label = label
        self.value = value
        self.details = details
        self.annotation = annotation
        self.kind = kind
        self.on_select_confirmed = on_select_confirmed


class QuickSelect:
    """
    This class can be used to perform a quick select flow.

    By using an ListInputHandler instead of window.show_quick_panel advanced features like
    multi select are possible.
    """

    def __init__(
        self,
        window: Optional[sublime.Window],
        items: List[SelectableItem],
        preselect_index: int = 0,
        placeholder: str = "",
        multi_select: bool = False,
    ):
        self.window = window or sublime.active_window()
        self.items = items
        self.preselect_index = preselect_index
        self.placeholder = placeholder
        self.multi_select = multi_select

        # Used here as Future
        self.promise = Promise(
            lambda _: None
        )  # type: Promise[Optional[List[SelectableItem]]]

    def show(self) -> Promise[Optional[List[SelectableItem]]]:
        return _ListInputHandler(self).show()


class _ListInputHandler(sublime_plugin.ListInputHandler):
    """
    The ListInputHandler that is returned from the dummy command "JdtlsQuickSelectCommand".
    """

    # TODO: Is locking necessary?
    __pending_list_input_handler = None  # type: Optional["_ListInputHandler"]

    @classmethod
    def _consume_pending(cls) -> Optional["_ListInputHandler"]:
        """
        Returns a pending quick select and sets it to none.
        """
        pending_list_input_handler = cls.__pending_list_input_handler
        cls.__pending_list_input_handler = None
        return pending_list_input_handler

    @classmethod
    def _has_pending(cls) -> bool:
        return cls.__pending_list_input_handler is not None

    def __init__(self, context: QuickSelect):
        self.context = context
        self.finished = False
        self.selected_indices_stack = []  # type: List[int]

    def show(self) -> Promise[Optional[List[SelectableItem]]]:
        """
        Shows the dialog and returns promise of the selection.

        The promise returns None if the selection was canceled.
        """
        if self.__class__._has_pending():
            raise ValueError("There is already an input handler pending.")
        self.__class__.__pending_list_input_handler = self
        _show_overlay(self.context.window)
        return self.context.promise

    def placeholder(self) -> str:
        return self.context.placeholder

    def initial_text(self) -> str:
        return ""

    def initial_selection(self):
        return []

    def list_items(self):
        # Value is set to an positive index to self.context.items
        # Value is -1 to signal "confirm"
        list_input_items = []

        if self.context.multi_select:
            list_input_items.append(
                sublime.ListInputItem(
                    "Confirm", -1, "", "Accept this selection", sublime.KIND_AMBIGUOUS
                )
            )
        for i, item in enumerate(self.context.items):
            if i not in self.selected_indices_stack:
                list_input_items.append(
                    sublime.ListInputItem(
                        item.label,
                        i,
                        item.details,
                        item.annotation,
                        item.kind,
                    )
                )
        preselect_index = 0 if len(self.selected_indices_stack) else self.context.preselect_index
        if self.context.multi_select:
            # Shift because of "Confirm" item
            preselect_index += 1
        return (list_input_items, preselect_index)

    def cancel(self) -> None:
        if self.selected_indices_stack:
            self.selected_indices_stack.pop()
        else:
            self.context.promise._do_resolve(None)
            sublime.set_timeout(lambda: _hide_overlay(self.context.window))

    def confirm(self, v: int) -> None:
        if v == -1:
            self.finished = True
        else:
            self.selected_indices_stack.append(v)

        if not self.context.multi_select:
            self.finished = True

        if self.finished:
            selection = []
            for index in self.selected_indices_stack:
                item = self.context.items[index]
                item.on_select_confirmed()
                selection.append(item)
            self.context.promise._do_resolve(selection)

    def next_input(
        self, args: Dict[str, Any]
    ) -> Optional[sublime_plugin.CommandInputHandler]:
        return None if self.finished else self


class JdtlsInputCommand(sublime_plugin.WindowCommand):
    """
    This is a dummy command to get the ListInputHandler to show.
    """

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        pending_list_input_handler = _ListInputHandler._consume_pending()

        if not pending_list_input_handler:
            raise ValueError("No pending list input handler.")

        return pending_list_input_handler

    def run(self, **args):
        # This is a dummpy command that is just used to get the ListInputHandler shown.
        ...

    def is_visible(self):
        return _ListInputHandler._has_pending()


def _hide_overlay(window):
    window.run_command(
        "show_overlay",
        {
            "overlay": "command_palette",
            "text": "",
        },
    )
    window.run_command(
        "hide_overlay",
        {
            "overlay": "command_palette",
        },
    )


def _show_overlay(window):
    # First hide all open overlays
    _hide_overlay(window)
    # Then show our own overlay
    window.run_command(
        "show_overlay",
        {
            "overlay": "command_palette",
            "command": "jdtls_input",
        },
    )
