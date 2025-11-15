from gi.repository import GObject, Gtk, Pango  # type: ignore

from pattern_renamer.main.types.mistakes import RenameDestinationMistake
from pattern_renamer.main.ui.widget_builder.widget_builder import (
    Children,
    InboundProperty,
    Properties,
    build,
)


class RenameItemData(GObject.GObject):
    """Data object for rename item widget"""

    picked_path: str = GObject.Property(type=str)  # type: ignore
    renamed_path: str = GObject.Property(type=str)  # type: ignore
    mistake: RenameDestinationMistake | None = GObject.Property(type=object)  # type: ignore

    def __init__(
        self,
        picked_path: str,
        renamed_path: str,
        mistake: RenameDestinationMistake | None = None,
    ) -> None:
        super().__init__()
        self.picked_path = picked_path
        self.renamed_path = renamed_path
        self.mistake = mistake


class RenameItemWidget(Gtk.Box):
    """Rename item widget"""

    # --- Inbound properties

    __mistake: RenameDestinationMistake | None = None

    @GObject.Property(type=object)
    def mistake(self) -> RenameDestinationMistake | None:
        return self.__mistake

    @mistake.setter
    def mistake_setter(self, value: RenameDestinationMistake | None) -> None:
        self.__mistake = value
        if value:
            self.__mistake_label.set_text(value.message)
            self.__mistake_revealer.set_reveal_child(True)
        else:
            self.__mistake_revealer.set_reveal_child(False)

    picked_path = GObject.Property(type=str, default="")
    renamed_path = GObject.Property(type=str, default="")

    # ---

    __picked_label: Gtk.Label
    __renamed_label: Gtk.Label
    __separator: Gtk.Label
    __mistake_label: Gtk.Label
    __mistake_revealer: Gtk.Revealer

    def __wrap_label_for_sizing(self, widget: Gtk.Widget) -> Gtk.Widget:
        return build(
            Gtk.ScrolledWindow
            + Properties(
                hscrollbar_policy=Gtk.PolicyType.NEVER,
                vscrollbar_policy=Gtk.PolicyType.NEVER,
            )
            + Children(widget)
        )

    def __build(self) -> None:
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(6)

        label_props = Properties(
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0.0,
            hexpand=True,
            ellipsize=Pango.EllipsizeMode.NONE,
        )

        self.__picked_label = build(
            Gtk.Label
            + label_props
            + Properties(
                valign=Gtk.Align.START,
                selectable=True,
            )
            + InboundProperty(
                source=self,
                source_property="picked-path",
                target_property="label",
            )
        )

        self.__renamed_label = build(
            Gtk.Label
            + label_props
            + Properties(
                valign=Gtk.Align.START,
            )
            + InboundProperty(
                source=self,
                source_property="renamed-path",
                target_property="label",
            )
        )

        self.__separator = build(
            Gtk.Label
            + Properties(
                css_classes=["separator"],
                label="→",
                valign=Gtk.Align.START,
                hexpand=False,
            )
        )

        center_box = build(
            Gtk.CenterBox
            + Children(
                self.__wrap_label_for_sizing(self.__picked_label),
                self.__separator,
                self.__wrap_label_for_sizing(self.__renamed_label),
            )
        )

        self.__mistake_label = build(
            Gtk.Label
            + Properties(
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                ellipsize=Pango.EllipsizeMode.NONE,
                halign=Gtk.Align.START,
            )
        )

        mistake_line = build(
            Gtk.Box
            + Properties(
                orientation=Gtk.Orientation.HORIZONTAL,
                css_classes=["error"],
                spacing=6,
            )
            + Children(
                Gtk.Image + Properties(icon_name="dialog-warning-symbolic"),
                self.__mistake_label,
            )
        )

        self.__mistake_revealer = build(
            Gtk.Revealer
            + Properties(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
            + Children(mistake_line)
        )

        self.append(center_box)
        self.append(self.__mistake_revealer)

    def __init__(self) -> None:
        self.set_css_name("rename-item")
        super().__init__()
        self.__build()


class RenameItemLifeCycleManager:
    """Class in charge of managing ListItem lifecycle for path widgets"""

    def attach_to(self, signal_factory: Gtk.SignalListItemFactory):
        """Attach the builder to the factory's signals"""
        signal_factory.connect("bind", self.__on_bind)
        signal_factory.connect("setup", self.__on_setup)

    def __on_setup(self, factory: Gtk.SignalListItemFactory, item: Gtk.ListItem):
        item.set_child(RenameItemWidget())

    def __on_bind(self, factory: Gtk.SignalListItemFactory, item: Gtk.ListItem):
        widget: RenameItemWidget = item.get_child()  # type: ignore
        data: RenameItemData = item.get_item()  # type: ignore

        widget.picked_path = data.picked_path
        widget.renamed_path = data.renamed_path
        widget.mistake = data.mistake
