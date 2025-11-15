import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable, Generic, Self, TypeVar

from gi.repository import Adw, GObject, Gtk  # type: ignore
from gi.repository.Gtk import Widget  # type: ignore

_BuiltWidget = TypeVar("_BuiltWidget", bound=Widget)


@dataclass
class InboundBinding:
    source: GObject.Object
    source_property: str
    target_property: str
    flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT


@dataclass
class OutboundBinding:
    source_property: str
    target: GObject.Object
    target_property: str
    flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT


Binding = InboundBinding | OutboundBinding


class WidgetBuilder(Generic[_BuiltWidget]):
    """
    Builder pattern to sequentially create Gtk Widget subclasses

    `WidgetBuilder`s may be added as children to other `WidgetBuilder`s as they
    are callables that return `Widget`.
    """

    __widget_class: type[_BuiltWidget]
    __arguments: dict[str, Any]
    __handlers: dict[str, Any]
    __properties: dict[str, Any]
    __children: list["WidgetBuilder | Widget | None"]
    __typed_children: list[tuple[str, "WidgetBuilder | Widget"]]
    __property_bindings: list[Binding]

    def __init__(self, widget_class: None | type[_BuiltWidget] = None) -> None:
        super().__init__()
        if widget_class is not None:
            self.set_widget_class(widget_class)
        self.__arguments = {}
        self.__handlers = {}
        self.__properties = {}
        self.__children = []
        self.__typed_children = []
        self.__property_bindings = []

    # Adders / Setters

    def set_widget_class(self, widget_class: type[_BuiltWidget]) -> Self:
        self.__widget_class = widget_class
        return self

    def add_arguments(self, **arguments: Any) -> Self:
        self.__arguments |= arguments
        return self

    def add_properties(self, **properties: Any) -> Self:
        self.__properties |= properties
        return self

    def add_handlers(self, **signal_handlers: Callable) -> Self:
        self.__handlers |= signal_handlers
        return self

    def add_children(self, *children: "WidgetBuilder | Widget | None") -> Self:
        """
        Add children to the widget.

        Children may be `Widget` instances, or any callable producing them.
        This includes `WidgetBuilder`, as calling it is an alias for `build()`.

        Cases depending on the built widget:
        - Receives a single child: Passing multiple will raise a ValueError.
        - Receives a finite number of children: Children will be added, `None` may be used to fill empty spaces
            (eg. the start and title of a `Adw.HeaderBar` when only the end is to be set)
        - Receives many children: all of them will be added.
        """
        self.__children.extend(children)
        return self

    def add_typed_children(
        self, *typed_children: tuple[str, "WidgetBuilder | Widget"]
    ) -> Self:
        """
        Add a child, with a given type.

        Useful for cases where a `Widget` may receive children in multiple places,
        with a default.
        """
        self.__typed_children.extend(typed_children)
        return self

    def add_property_bindings(self, *bindings: Binding) -> Self:
        """Add a property binding to the widget builder."""
        self.__property_bindings.extend(bindings)
        return self

    # Getters

    def get_widget_class(self) -> type[_BuiltWidget]:
        return self.__widget_class

    def get_arguments(self) -> dict[str, Any]:
        return self.__arguments

    def get_properties(self) -> dict[str, Any]:
        return self.__properties

    def get_handlers(self) -> dict[str, Any]:
        return self.__handlers

    def get_children(self) -> list["WidgetBuilder | Widget | None"]:
        return self.__children

    def get_typed_children(self) -> list[tuple[str, "WidgetBuilder | Widget"]]:
        return self.__typed_children

    def get_property_bindings(self) -> list[Binding]:
        return self.__property_bindings

    # Build helpers

    def __apply_properties(self, widget: _BuiltWidget) -> None:
        """Apply a set of properties to a widget"""
        for key, value in self.__properties.items():
            widget.set_property(key.replace("_", "-"), value)

    def __apply_handlers(self, widget: Widget) -> None:
        for signal, handler in self.__handlers.items():
            widget.connect(signal.replace("_", "-"), handler)

    def __check_no_null_children(
        self, widget: Widget, children: Sequence[Widget | None]
    ) -> Sequence[Widget]:
        """Helper function to check that the passed children contains no None"""
        for child in children:
            if child is None:
                raise ValueError(
                    "WidgetBuilder may not receive None children for %s"
                    % widget.__class__.__name__
                )
        return children  # type: ignore

    def __check_n_children(
        self, widget: Widget, n: int, children: Sequence[Widget | None]
    ) -> None:
        """Helper function to check that the passed children are of length `n`"""
        if len(children) != n:
            raise ValueError(
                "Widget %s may only receive %d children, passed %d for this widget type"
                % (widget.__class__.__name__, n, len(children))
            )

    def __resolve_children(
        self, children: Sequence["WidgetBuilder | Widget | None"]
    ) -> Sequence[Widget | None]:
        """Resolve `WidgetProducer` children by calling them and producing their `Widget`"""
        return [
            (build(child) if isinstance(child, WidgetBuilder) else child)
            for child in children
        ]

    def __apply_children(self, widget: Widget) -> None:
        # Resolve children from producers
        resolved = self.__resolve_children(self.__children)

        # Short circuit
        if not resolved:
            return

        # Gtk.Box, Gtk.ListBox
        # Containers that use the append method to add N children
        if isinstance(widget, Gtk.Box) or isinstance(widget, Gtk.ListBox):
            for child in self.__check_no_null_children(widget, resolved):
                widget.append(child)

        # Adw.PreferencesGroup
        elif isinstance(widget, Adw.PreferencesGroup):
            for child in self.__check_no_null_children(widget, resolved):
                widget.add(child)

        # Adw.ApplicationWindow
        elif isinstance(widget, Adw.ApplicationWindow):
            self.__check_n_children(widget, 1, resolved)
            widget.set_content(resolved[0])

        # Adw.ToolbarView
        # Note: to set top and bottom toolbars, use the TypedChild method
        elif isinstance(widget, Adw.ToolbarView):
            try:
                self.__check_n_children(widget, 1, resolved)
            except ValueError as e:
                logging.info("Adw.ToolbarView can only receive one untyped child.")
                logging.info("To set top and bottom bars, use TypedChild")
                raise e
            widget.set_content(resolved[0])

        # Gtk.CenterBox
        elif isinstance(widget, Gtk.CenterBox):
            try:
                self.__check_n_children(widget, 3, resolved)
            except ValueError as e:
                logging.info("Gtk.CenterBox must receive 3 untyped children.")
                logging.info("To set children individually, use TypedChild")
                raise e
            start, center, end = resolved
            widget.set_start_widget(start)
            widget.set_center_widget(center)
            widget.set_end_widget(end)

        # Adw.ViewStack, Adw.NavigationView
        elif isinstance(widget, Adw.ViewStack) or isinstance(
            widget, Adw.NavigationView
        ):
            for child in self.__check_no_null_children(widget, resolved):
                widget.add(child)

        # Adw.OverlaySplitView
        elif isinstance(widget, Adw.OverlaySplitView):
            self.__check_n_children(widget, 2, resolved)
            sidebar, content = resolved
            if isinstance(sidebar, Widget):
                widget.set_sidebar(sidebar)
            if isinstance(content, Widget):
                widget.set_content(content)

        # Gtk.HeaderBar, Adw.HeaderBar
        elif isinstance(widget, Gtk.HeaderBar) or isinstance(widget, Adw.HeaderBar):
            self.__check_n_children(widget, 1, resolved)
            widget.set_title_widget(resolved[0])

        # Any widget with "set_child"
        elif getattr(widget, "set_child", None) is not None:
            self.__check_n_children(widget, 1, resolved)
            widget.set_child(resolved[0])  # type: ignore

        # Cannot set children
        else:
            raise TypeError(
                'Widgets of type "%s" cannot receive children'
                % widget.__class__.__name__
            )

    def __resolve_typed_children(
        self, typed_children: Sequence[tuple[str, "WidgetBuilder | Widget"]]
    ) -> Sequence[tuple[str, Widget]]:
        return [
            (type_, build(child) if isinstance(child, WidgetBuilder) else child)
            for type_, child in typed_children
        ]

    def __apply_typed_children(self, widget: _BuiltWidget) -> None:
        resolved = self.__resolve_typed_children(self.__typed_children)

        # Shortcut, there is no typed child
        if not resolved:
            return

        # Adw.ToolbarView
        if isinstance(widget, Adw.ToolbarView):
            for t, child in resolved:
                if t == "top":
                    widget.add_top_bar(child)
                if t == "bottom":
                    widget.add_bottom_bar(child)
                if t == "content":
                    widget.set_content(child)

        # Adw.HeaderBar
        elif isinstance(widget, Adw.HeaderBar):
            for t, child in resolved:
                if t == "start":
                    widget.pack_start(child)
                if t == "end":
                    widget.pack_end(child)
                if t == "title":
                    widget.set_title_widget(child)

        # Gtk.ActionBar
        elif isinstance(widget, Gtk.ActionBar):
            for t, child in resolved:
                if t == "start":
                    widget.pack_start(child)
                if t == "end":
                    widget.pack_end(child)
                if t == "center":
                    widget.set_center_widget(child)

        # Adw.ActionRow
        # Adw.EntryRow
        elif isinstance(widget, Adw.ActionRow) or isinstance(widget, Adw.EntryRow):
            for t, child in resolved:
                if t == "prefix":
                    widget.add_prefix(child)
                if t == "suffix":
                    widget.add_suffix(child)

        # Adw.OverlaySplitView
        elif isinstance(widget, Adw.OverlaySplitView):
            for t, child in resolved:
                if t == "sidebar":
                    widget.set_sidebar(child)
                if t == "content":
                    widget.set_content(child)

        # Adw.PreferencesGroup
        elif isinstance(widget, Adw.PreferencesGroup):
            for t, child in resolved:
                if t == "header-suffix":
                    widget.set_header_suffix(child)

        # Gtk.CenterBox
        elif isinstance(widget, Gtk.CenterBox):
            for t, child in resolved:
                if t == "start":
                    widget.set_start_widget(child)
                if t == "center":
                    widget.set_center_widget(child)
                if t == "end":
                    widget.set_end_widget(child)

    def __apply_property_bindings(self, widget: _BuiltWidget) -> None:
        """Apply property bindings to the widget"""
        for binding in self.__property_bindings:
            match binding:
                case InboundBinding():
                    binding.source.bind_property(
                        binding.source_property,
                        widget,
                        binding.target_property,
                        binding.flags,
                    )
                case OutboundBinding():
                    widget.bind_property(
                        binding.source_property,
                        binding.target,
                        binding.target_property,
                        binding.flags,
                    )
                case _:
                    message = "Unknown binding type %s" % binding.__class__.__name__
                    raise TypeError(message)

    def build(self) -> _BuiltWidget:
        """Build the widget"""
        if not callable(self.__widget_class):
            raise ValueError("Cannot build without a widget class")
        widget = self.__widget_class(**self.__arguments)
        self.__apply_handlers(widget)
        self.__apply_properties(widget)
        self.__apply_children(widget)
        self.__apply_typed_children(widget)
        self.__apply_property_bindings(widget)
        return widget

    def __add__(
        self, other: "WidgetBuilder[_BuiltWidget]"
    ) -> "WidgetBuilder[_BuiltWidget]":
        return (
            WidgetBuilder()
            .set_widget_class(self.get_widget_class())
            # Add data from self
            .add_arguments(**self.get_arguments())
            .add_handlers(**self.get_handlers())
            .add_properties(**self.get_properties())
            .add_children(*self.get_children())
            .add_typed_children(*self.get_typed_children())
            .add_property_bindings(*self.get_property_bindings())
            # Add data from other
            .add_arguments(**other.get_arguments())
            .add_handlers(**other.get_handlers())
            .add_properties(**other.get_properties())
            .add_children(*other.get_children())
            .add_typed_children(*other.get_typed_children())
            .add_property_bindings(*other.get_property_bindings())
        )

    def __radd__(self, other: type[Widget]) -> "WidgetBuilder":
        # fmt: off
        """
        Applies to a Widget class to return a new WidgetBuilder.

        Will wrap the `Widget` class into a `WidgetBuilder` and recurse the "add" operation.  
        Enables the following syntax:  
        Gtk.Button + Properties(css_classes=["suggested-action"])
        """
        # fmt: on
        if issubclass(other, Widget):
            builder = WidgetBuilder()
            builder.set_widget_class(other)
            return builder + self


class Arguments(WidgetBuilder):
    """A dict of constructor arguments to pass to a builder object"""

    def __init__(self, **arguments: Any) -> None:
        super().__init__()
        self.add_arguments(**arguments)


class Properties(WidgetBuilder):
    """A dict of properties to pass to a builder object"""

    def __init__(self, **properties: Any) -> None:
        super().__init__()
        self.add_properties(**properties)


class Handlers(WidgetBuilder):
    """A dict of signal handlers to pass to a builder object"""

    def __init__(self, **handlers: Callable) -> None:
        super().__init__()
        self.add_handlers(**handlers)


class Reemit(WidgetBuilder):
    """Attach a signal handler that re-emits the signal on another object"""

    def __init__(
        self,
        signal: str,
        target: GObject.Object,
        target_signal: str | None = None,
    ) -> None:
        super().__init__()

        def handler(_source, *args):
            target.emit(target_signal or signal, *args)

        self.add_handlers(**{signal: handler})


class Children(WidgetBuilder):
    """A list of children to pass to a builder object"""

    def __init__(self, *children: "WidgetBuilder | Widget | None") -> None:
        super().__init__()
        self.add_children(*children)


class TypedChild(WidgetBuilder):
    """A single typed child to pass to a builder object"""

    def __init__(self, t: str, child: "WidgetBuilder | Widget") -> None:
        super().__init__()
        self.add_typed_children((t, child))


class OutboundProperty(WidgetBuilder):
    """
    A property binding to pass to a builder object.

    Will replicate changes from source_property on the built widget to target_property on the target object.
    """

    def __init__(
        self,
        source_property: str,
        target: GObject.Object,
        target_property: str,
        flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT,
    ) -> None:
        super().__init__()
        self.add_property_bindings(
            OutboundBinding(
                source_property=source_property,
                target=target,
                target_property=target_property,
                flags=flags,
            )
        )


class InboundProperty(WidgetBuilder):
    """
    A property binding to pass to a builder object.

    Will replicate changes made to source_property on the source object to the built widget's target_property.
    """

    def __init__(
        self,
        source: GObject.Object,
        source_property: str,
        target_property: str,
        flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT,
    ) -> None:
        super().__init__()
        self.add_property_bindings(
            InboundBinding(
                source_property=source_property,
                source=source,
                target_property=target_property,
                flags=flags,
            )
        )


def build(builder: type[_BuiltWidget] | WidgetBuilder[_BuiltWidget]) -> _BuiltWidget:
    """
    Function that builds a `WidgetBuilder`.

    This is just syntactic sugar around `WidgetBuilder.build()`.
    If passed a `Widget` subclass directly, will wrap it in a `WidgetBuilder`
    and build it.
    """
    if isinstance(builder, WidgetBuilder):
        return builder.build()
    if issubclass(builder, Widget):
        return WidgetBuilder(builder).build()
    raise TypeError("Cannot build type %s" % builder.__class__.__name__)
