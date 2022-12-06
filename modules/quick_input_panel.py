"""
Implements an high level API to query a selection or a text from an user.

Usage:
QuickSelect(...).show().then( do_something_with_selection )
or:
QuickTextInput(...).show().then( do_something_with_text )

Inspired by https://github.com/daveleroy/sublime_debugger/blob/master/modules/ui/input.py
"""

from LSP.plugin.core.promise import Promise
from LSP.plugin.core.typing import List, Optional, Dict, Any, Callable, Tuple, Union

import sublime
import sublime_plugin


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

        :param      label:      The label that is matched against the input
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
    This class can be used to query a selection from the user.
    """

    def __init__(
        self,
        window: Optional[sublime.Window],
        items: List[SelectableItem],
        preselect_index: int = 0,
        placeholder: str = "",
        multi_select: bool = False,
    ):
        self._window = window or sublime.active_window()
        self._items = items
        self._preselect_index = preselect_index
        self._placeholder = placeholder
        self._multi_select = multi_select

        # Used here as Future
        self._promise = Promise(
            lambda _: None
        )  # type: Promise[Optional[List[SelectableItem]]]

    def show(self) -> Promise[Optional[List[SelectableItem]]]:
        JdtlsInputCommand.enqueue(_ListInputHandler(self))
        JdtlsInputCommand.show(self._window)
        return self._promise


class QuickTextInput:
    """
    This class can be used to query text from the user.
    """

    def __init__(
        self,
        window: Optional[sublime.Window],
        placeholder: str = "",
        initial_text: str = "",
        validate: Optional[Callable[[str], bool]] = None,
        preview: Optional[Callable[[str], Union[str, sublime.Html]]] = None
    ):
        self._window = window or sublime.active_window()
        self._placeholder = placeholder
        self._initial_text = initial_text
        self._validate = validate
        self._preview = preview
        # Used here as Future
        self._promise = Promise(
            lambda _: None
        )  # type: Promise[Optional[str]]

    def show(self) -> Promise[Optional[str]]:
        JdtlsInputCommand.enqueue(_TextInputHandler(self))
        JdtlsInputCommand.show(self._window)
        return self._promise


class _TextInputHandler(sublime_plugin.TextInputHandler):

    def __init__(self, context: QuickTextInput):
        self.context = context

    def placeholder(self) -> str:
        return self.context._placeholder

    def initial_text(self) -> str:
        return self.context._initial_text

    def confirm(self, v: str) -> None:
        self.context._promise._do_resolve(v)

    def cancel(self) -> None:
        self.context._promise._do_resolve(None)

    def validate(self, text: str) -> bool:
        return self.context._validate(text) if self.context._validate else True

    def preview(self, text: str) -> Union[str, sublime.Html]:
        return self.context._preview(text) if self.context._preview else ""


class _ListInputHandler(sublime_plugin.ListInputHandler):
    """
    The ListInputHandler that is returned from the dummy command "JdtlsQuickSelectCommand".
    """

    def __init__(self, context: QuickSelect):
        self.context = context
        self.finished = False
        self.selected_indices_stack = []  # type: List[int]

    def placeholder(self) -> str:
        return self.context._placeholder

    def initial_text(self) -> str:
        return ""

    def initial_selection(self):
        return []

    def list_items(self):
        # Value is set to an positive index to self.context.items
        # Value is -1 to signal "confirm"
        list_input_items = []

        if self.context._multi_select:
            list_input_items.append(
                sublime.ListInputItem(
                    "Confirm", -1, "", "Accept this selection", sublime.KIND_AMBIGUOUS
                )
            )
        for i, item in enumerate(self.context._items):
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
        preselect_index = (
            0 if len(self.selected_indices_stack) else self.context._preselect_index
        )
        if self.context._multi_select:
            # Shift because of "Confirm" item
            preselect_index += 1
        return (list_input_items, preselect_index)

    def cancel(self) -> None:
        if self.selected_indices_stack:
            self.selected_indices_stack.pop()
        else:
            self.context._promise._do_resolve(None)
            # calling _hide_overlay directly crashes sublime :(
            sublime.set_timeout(lambda: _hide_overlay(self.context._window))

    def confirm(self, v: int) -> None:
        if v == -1:
            self.finished = True
        else:
            self.selected_indices_stack.append(v)

        if not self.context._multi_select:
            self.finished = True

        if self.finished:
            selection = []
            for index in self.selected_indices_stack:
                item = self.context._items[index]
                item.on_select_confirmed()
                selection.append(item)
            self.context._promise._do_resolve(selection)

    def next_input(
        self, args: Dict[str, Any]
    ) -> Optional[sublime_plugin.CommandInputHandler]:
        return None if self.finished else self


class JdtlsInputCommand(sublime_plugin.WindowCommand):
    """
    This is a dummy command to get the ListInputHandler to show.
    """

    # TODO: Is locking necessary?
    __pending_list_input_handler = (
        None
    )  # type: Optional[sublime_plugin.CommandInputHandler]

    @classmethod
    def _consume_pending(cls) -> Optional[sublime_plugin.CommandInputHandler]:
        """
        Returns a pending quick select and sets it to none.
        """
        pending_list_input_handler = cls.__pending_list_input_handler
        cls.__pending_list_input_handler = None
        return pending_list_input_handler

    @classmethod
    def _has_pending(cls) -> bool:
        return cls.__pending_list_input_handler is not None

    @classmethod
    def enqueue(cls, input_handler: sublime_plugin.CommandInputHandler):
        if cls._has_pending():
            raise ValueError("There is already an input handler pending.")
        cls.__pending_list_input_handler = input_handler

    @classmethod
    def show(cls, window: sublime.Window):
        if not cls._has_pending():
            raise ValueError("There is no command input handler pending")
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

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        pending_list_input_handler = self.__class__._consume_pending()

        if not pending_list_input_handler:
            raise ValueError("No pending list input handler.")

        return pending_list_input_handler

    def run(self, **args):
        # This is a dummy command that is just used to get the CommandInputHandler shown.
        ...

    def is_visible(self):
        return self.__class__._has_pending()


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
