import sys
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QTranslator, QLibraryInfo, QEvent, QTimer
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QFont, QPen, QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QSlider, QColorDialog, QFrame,
    QStackedWidget, QMessageBox, QComboBox, QScrollArea, QGraphicsColorizeEffect, QDialog, QDialogButtonBox)
from .model import State, Scheme
from .i18n import translate
from .bridge_panel import BridgePanel

ROOT = Path(__file__).resolve().parent.parent

def default_state_path():
    if getattr(sys, 'frozen', False):
        return Path.home() / 'Library' / 'Application Support' / 'PhiHue' / 'state.json'
    return ROOT / 'data' / 'state.json'

class SettingsButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(32, 32)
        self.setToolTip('Configuración')
        self.setAccessibleName('Abrir configuración')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(0.75, 0.75)
        p.setPen(QPen(QColor('#d3c4ff' if self.hasFocus() else '#363943'), 1))
        p.setBrush(QColor('#30303b' if self.underMouse() else '#1d1e24'))
        p.drawRoundedRect(QRectF(1, 1, 40, 40), 12, 12)
        p.translate(21, 21)
        p.setPen(QPen(QColor('#ddd1f6'), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(-7, -7, 14, 14))
        for _ in range(8):
            p.drawLine(0, -8, 0, -11)
            p.rotate(45)
        p.setPen(QPen(QColor('#ddd1f6'), 2))
        p.drawEllipse(QRectF(-2.5, -2.5, 5, 5))

class SaveButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#d3c4ff'), 0.75))
        p.setBrush(QColor('#30303b' if self.underMouse() else '#1d1e24'))
        p.drawRoundedRect(QRectF(1, 1, 30, 30), 9, 9)
        p.setPen(QPen(QColor('#ddd1f6'), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(8, 7, 16, 18), 1, 1)
        p.drawRect(QRectF(11, 7, 9, 6))
        p.drawRect(QRectF(11, 18, 10, 7))


class SchemeCard(QPushButton):
    def __init__(self, number):
        super().__init__()
        self.number = number
        self.scheme = None
        self.powered = True
        self.setCheckable(True)
        self.setMinimumSize(138, 154)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        if self.scheme is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        for position, color in zip((0, 1), self.scheme.colors):
            c = QColor(color)
            c = QColor.fromRgbF(c.redF() * .22 + .065, c.greenF() * .22 + .065, c.blueF() * .22 + .075)
            gradient.setColorAt(position, c)
        p.setBrush(gradient)
        p.setPen(QPen(QColor('#c9b9ff' if self.isChecked() else '#697183' if self.underMouse() else '#363943'), 2 if self.isChecked() else 1))
        p.drawRoundedRect(rect, 18, 18)
        for index, color in enumerate(self.scheme.colors):
            x = self.width() / 2 - 24 + index * 48
            # Two small lamp silhouettes, each using its exact stored RGB.
            p.setPen(Qt.PenStyle.NoPen)
            actual = getattr(self, 'actual_lights', None)
            p.setBrush(display_color(color, actual[index]['brightness'] if actual else self.scheme.brightnesses[index] if self.scheme.brightnesses else self.scheme.brightness, actual[index]['on'] if actual else self.scheme.powers[index] if self.scheme.powers else self.powered))
            p.drawRoundedRect(QRectF(x - 13, 53, 26, 30), 10, 10)
            p.setBrush(QColor('#b8b8c4'))
            p.drawRoundedRect(QRectF(x - 7, 86, 14, 4), 2, 2)
            p.drawRoundedRect(QRectF(x - 5, 92, 10, 3), 1, 1)
        p.setPen(QColor('#f4f1fa'))
        p.setFont(QFont('Helvetica', 12, QFont.Weight.Medium))
        name = p.fontMetrics().elidedText(self.scheme.name, Qt.TextElideMode.ElideRight, self.width() - 24)
        p.drawText(QRectF(12, 114, self.width() - 24, 26), Qt.AlignmentFlag.AlignCenter, name)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#ffffff'), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 14, 14)


def display_color(color, brightness, powered):
    c = QColor(color)
    strength = brightness / 100 if powered else 0
    return QColor.fromRgbF(c.redF() * strength, c.greenF() * strength, c.blueF() * strength)


class PowerButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(76, 76)
        self.setAccessibleName('Encender o apagar ambos focos')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        p.setBrush(QColor('#b9a0f5' if active else '#282931'))
        p.setPen(QPen(QColor('#e2d6ff' if self.hasFocus() else '#b9a0f5' if active else '#565360'), 2))
        p.drawEllipse(QRectF(3, 3, 70, 70))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor('#241a36' if active else '#c8c1d3'), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(23, 23, 30, 30), 135 * 16, 270 * 16)
        p.drawLine(38, 19, 38, 36)


STYLE = """
    QWidget { color: #f0edf6; font-family: 'Helvetica'; font-size: 13px; }
    QMainWindow, QWidget#root { background: #141519; }
    QLabel { background: transparent; }
    QLabel#brand { font-size: 28px; font-weight: 700; }
    QLabel#sectionTitle { font-size: 15px; font-weight: 600; }
    QLabel#muted { color: #96939f; font-size: 12px; }
    QLabel#eyebrow { color: #aaa2ba; font-size: 11px; font-weight: 600; }
    QFrame#panel { background: #1d1e24; border: 1px solid #303038; border-radius: 20px; }
    QLineEdit { background: #25262e; border: 1px solid #3a3945; border-radius: 9px; padding: 10px 12px; }
    QComboBox { background: #25262e; border: 1px solid #3a3945; border-radius: 9px; padding: 10px 12px; }
    QComboBox QAbstractItemView { background: #25262e; selection-background-color: #514269; }
    QLineEdit:focus { border-color: #b9a0f5; }
    QPushButton { border-radius: 12px; padding: 12px; }
    QPushButton:focus { border: 1px solid #d3c4ff; }
    QScrollArea { background: #141519; }
    QScrollBar:vertical { background: #141519; width: 10px; }
    QScrollBar::handle:vertical { background: #45414f; border-radius: 5px; min-height: 28px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #141519; }
    QSlider::groove:horizontal { height: 6px; background: #3b3946; border-radius: 3px; }
    QSlider::sub-page:horizontal { background: #b9a0f5; border-radius: 3px; }
    QSlider::handle:horizontal { width: 18px; margin: -6px 0; background: #eee5ff; border-radius: 9px; }
"""

class Window(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        path = default_state_path() if path is None else path
        self.scene_drafts = {}
        self.actual = None
        self.actual_view = True
        self.path = path
        self.text_bindings = []
        self.qt_translator = QTranslator(self)
        warning = ''
        try:
            self.state = State.load(path)
        except FileNotFoundError:
            self.state = State()
        except (ValueError, TypeError, KeyError, AssertionError, OSError):
            self.state = State()
            warning = 'No se pudo leer el guardado. Se cargaron los valores iniciales.'
        for scheme in self.state.schemes:
            scheme.linked = False
        self.setWindowTitle('PhiHue')
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setStyleSheet(STYLE)
        container = QWidget()
        container.setObjectName('root')
        self.main_page = container
        container.installEventFilter(self)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.pages.addWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QLabel('PhiHue')
        title.setObjectName('brand')
        title.setFont(QFont('Helvetica', 26, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        badge = QLabel()
        self.badge = badge
        badge.setObjectName('muted')
        header.addWidget(badge)
        self.settings_button = SettingsButton()
        self.settings_button.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        header.addWidget(self.settings_button)
        layout.addLayout(header)
        self.connection_notice = QLabel()
        self.connection_notice.setWordWrap(True)
        layout.addWidget(self.connection_notice)
        self.controls = QWidget()
        layout.addWidget(self.controls)
        layout = QVBoxLayout(self.controls)
        layout.setContentsMargins(0, 0, 0, 0)
        self.disabled_effect = QGraphicsColorizeEffect(self.controls)
        self.disabled_effect.setColor(QColor('#202020'))
        self.disabled_effect.setStrength(1)
        self.controls.setGraphicsEffect(self.disabled_effect)
        caption = QLabel()
        self.bind(caption.setText, 'TUS AMBIENTES')
        caption.setObjectName('eyebrow')
        caption.setContentsMargins(0, 8, 0, 12)
        layout.addWidget(caption)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.actual_button = SchemeCard(0)
        self.actual_button.clicked.connect(lambda: self.bridge_panel.return_to_controls())
        self.bind(self.actual_button.setToolTip, 'Consultar el estado actual sin modificar las luces')
        row.addWidget(self.actual_button, 1)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet('color: #4b435c;')
        row.addWidget(separator)
        self.buttons = []
        for i in range(5):
            button = SchemeCard(i + 1)
            button.clicked.connect(lambda checked=False, index=i: self.select(index))
            row.addWidget(button, 1)
            self.buttons.append(button)
        layout.addLayout(row)
        panel = QFrame()
        self.scene_editor = panel
        panel.setObjectName('panel')
        editor = QVBoxLayout(panel)
        editor.setContentsMargins(24, 22, 24, 22)
        editor.setSpacing(20)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        label = QLabel()
        self.bind(label.setText, 'Personalizá tu ambiente')
        label.setObjectName('sectionTitle')
        label.setFont(QFont('Helvetica', 15, QFont.Weight.Medium))
        label.setFixedHeight(40)
        name_row.addWidget(label)
        name_row.addStretch()
        self.name = QLineEdit()
        self.bind(self.name.setAccessibleName, 'Nombre del esquema')
        self.name.setMaxLength(32)
        self.name.setFixedSize(230, 40)
        self.name.textEdited.connect(self.rename)
        name_row.addWidget(self.name)
        self.save_scene_button = SaveButton()
        self.bind(self.save_scene_button.setToolTip, 'Guardar ambiente')
        self.bind(self.save_scene_button.setAccessibleName, 'Guardar ambiente')
        self.save_scene_button.clicked.connect(self.save_scene)
        name_row.addWidget(self.save_scene_button)
        editor.addLayout(name_row)
        colors = QHBoxLayout()
        colors.setSpacing(14)
        self.color_buttons = []
        for i in range(2):
            button = QPushButton()
            button.setMinimumHeight(62)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, index=i: self.pick_color(index))
            colors.addWidget(button, 1)
            self.color_buttons.append(button)
        editor.addLayout(colors)
        copy_row = QVBoxLayout()
        copy_row.setSpacing(4)
        for source, label in [(0, '→'), (1, '←')]:
            button = QPushButton(label)
            button.setFixedSize(36, 29)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet('background: #30303b; color: #ddd1f6; padding: 0; border-radius: 8px; font-size: 18px;')
            self.bind(button.setToolTip, 'Copiar color del foco {source} al foco {target}', source=source + 1, target=2 - source)
            self.bind(button.setAccessibleName, 'Copiar color del foco {source} al foco {target}', source=source + 1, target=2 - source)
            button.clicked.connect(lambda checked=False, index=source: self.copy_color(index))
            copy_row.addWidget(button)
        colors.insertLayout(1, copy_row)
        brightness_row = QHBoxLayout()
        self.brightness_label = QLabel()
        self.brightness_label.setMinimumWidth(155)
        brightness_row.addWidget(self.brightness_label)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.bind(self.brightness.setAccessibleName, 'Brillo común de los dos focos')
        self.brightness.valueChanged.connect(self.adjust_brightness)
        brightness_row.addWidget(self.brightness)
        editor.addLayout(brightness_row)
        layout.addWidget(panel)
        self.actual_panel = QFrame()
        self.actual_panel.setObjectName('panel')
        actual_layout = QVBoxLayout(self.actual_panel)
        actual_layout.setContentsMargins(24, 22, 24, 22)
        actual_layout.setSpacing(20)
        title = QLabel()
        title.setObjectName('sectionTitle')
        title.setFont(QFont('Helvetica', 15, QFont.Weight.Medium))
        title.setFixedHeight(40)
        self.bind(title.setText, 'Personalizá tu ambiente')
        actual_header = QHBoxLayout()
        actual_header.addWidget(title)
        actual_header.addStretch()
        self.save_actual_button = SaveButton()
        self.bind(self.save_actual_button.setToolTip, 'Guardar en un ambiente')
        self.bind(self.save_actual_button.setAccessibleName, 'Guardar en un ambiente')
        self.save_actual_button.clicked.connect(self.save_actual_dialog)
        actual_header.addWidget(self.save_actual_button)
        actual_layout.addLayout(actual_header)
        self.actual_labels = []
        self.actual_sliders = []
        actual_columns = QHBoxLayout()
        actual_columns.setSpacing(14)
        for index in range(2):
            column = QVBoxLayout()
            column.setSpacing(16)
            label = QPushButton()
            label.clicked.connect(lambda checked=False, i=index: self.pick_actual_color(i))
            label.setMinimumHeight(62)
            column.addWidget(label)
            self.actual_labels.append(label)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            self.bind(slider.setAccessibleName, 'Brillo del foco {number}', number=index + 1)
            slider.valueChanged.connect(lambda value, i=index: self.edit_actual(i, brightness=value))
            column.addWidget(slider)
            self.actual_sliders.append(slider)
            actual_columns.addLayout(column, 1)
        actual_layout.addLayout(actual_columns)
        layout.addWidget(self.actual_panel)
        power_row = QHBoxLayout()
        power_row.addStretch()
        self.power = PowerButton()
        self.power.toggled.connect(self.toggle_power)
        power_row.addWidget(self.power)
        power_row.addStretch()
        layout.addLayout(power_row)
        self.status = QLabel(warning)
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        self.status.setVisible(bool(warning))
        layout.addWidget(self.status)
        self.build_settings_page()
        self.bind(self.settings_button.setToolTip, 'Configuración')
        self.bind(self.settings_button.setAccessibleName, 'Abrir configuración')
        self.bind(self.power.setAccessibleName, 'Encender o apagar ambos focos')
        if warning:
            self.bind(self.status.setText, warning)
        self.apply_language()
        self.ensurePolished()
        self.refresh()

    def eventFilter(self, obj, event):
        if obj is getattr(self, 'main_page', None) and event.type() == QEvent.Type.LayoutRequest:
            QTimer.singleShot(0, self.fit_window)
        return super().eventFilter(obj, event)

    def fit_window(self):
        self.controls.updateGeometry()
        height = max(self.main_page.sizeHint().height(), self.main_page.minimumSizeHint().height())
        if self.height() != height or self.width() != 980:
            self.setFixedSize(980, height)

    def tr_text(self, text, **values):
        return translate(self.state.language, text, **values)

    def bind(self, setter, text, **values):
        self.text_bindings.append((setter, text, values))
        setter(self.tr_text(text, **values))

    def apply_language(self):
        app = QApplication.instance()
        app.removeTranslator(self.qt_translator)
        if self.state.language == 'es':
            if self.qt_translator.load('qtbase_es', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(self.qt_translator)
        for setter, text, values in self.text_bindings:
            setter(self.tr_text(text, **values))
        self.language_selector.blockSignals(True)
        self.language_selector.setCurrentIndex(self.language_selector.findData(self.state.language))
        self.language_selector.blockSignals(False)
        self.bridge_panel.retranslate()
        self.refresh()

    def change_language(self):
        previous = self.state.language
        self.state.language = self.language_selector.currentData()
        try:
            self.state.save(self.path)
        except OSError as error:
            self.state.language = previous
            self.apply_language()
            QMessageBox.warning(self, self.tr_text('No se pudo guardar'), self.tr_text('No se pudo guardar: {error}', error=error))
            return
        self.apply_language()

    def build_settings_page(self):
        page = QWidget()
        page.setObjectName('root')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(24)
        header = QHBoxLayout()
        self.back_button = QPushButton()
        self.bind(self.back_button.setText, '← Volver')
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(lambda: self.bridge_panel.return_to_controls())
        header.addWidget(self.back_button)
        header.addStretch()
        layout.addLayout(header)
        title = QLabel()
        self.bind(title.setText, 'Configuración')
        title.setObjectName('brand')
        layout.addWidget(title)
        language_panel = QFrame()
        language_panel.setObjectName('panel')
        language_row = QHBoxLayout(language_panel)
        language_row.setContentsMargins(24, 20, 24, 20)
        language_label = QLabel()
        language_label.setObjectName('sectionTitle')
        self.bind(language_label.setText, 'Idioma')
        language_row.addWidget(language_label)
        language_row.addStretch()
        self.language_selector = QComboBox()
        self.language_selector.addItem('Español', 'es')
        self.language_selector.addItem('English', 'en')
        self.language_selector.setMinimumWidth(180)
        self.bind(self.language_selector.setAccessibleName, 'Idioma')
        language_label.setBuddy(self.language_selector)
        self.language_selector.currentIndexChanged.connect(self.change_language)
        language_row.addWidget(self.language_selector)
        layout.addWidget(language_panel)
        self.bridge_panel = BridgePanel(self)
        self.bridge_panel.mode_changed.connect(self.refresh)
        self.bridge_panel.control_error.connect(self.show_bridge_error)
        self.bridge_panel.control_success.connect(self.clear_bridge_error)
        layout.addWidget(self.bridge_panel)
        panel = QFrame()
        panel.setObjectName('panel')
        content = QVBoxLayout(panel)
        content.setContentsMargins(24, 24, 24, 24)
        content.setSpacing(16)
        heading = QLabel()
        self.bind(heading.setText, 'Restaurar valores iniciales')
        heading.setObjectName('sectionTitle')
        content.addWidget(heading)
        description = QLabel()
        self.bind(description.setText, 'Restaurá los cinco ambientes originales: nombres, colores, brillo y encendido. Se conserva el idioma elegido.')
        description.setWordWrap(True)
        description.setObjectName('muted')
        content.addWidget(description)
        self.reset_button = QPushButton()
        self.bind(self.reset_button.setText, 'Restaurar valores iniciales')
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet('background: #422b36; color: #ffd0dc;')
        self.reset_button.clicked.connect(self.reset_settings)
        content.addWidget(self.reset_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(panel)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)

    def reset_settings(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.tr_text('Restaurar valores iniciales'))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(self.tr_text('¿Querés borrar tu configuración guardada?'))
        dialog.setInformativeText(self.tr_text('Se perderán los nombres, colores y ajustes personalizados de todos los ambientes. Esta acción no se puede deshacer.'))
        restore = dialog.addButton(self.tr_text('Restaurar'), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(self.tr_text('Cancelar'), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        if dialog.clickedButton() != restore:
            return
        state = State(language=self.state.language, bridge=self.state.bridge)
        for scheme in state.schemes:
            scheme.linked = False
        try:
            state.save(self.path)
        except OSError as error:
            QMessageBox.warning(self, self.tr_text('No se pudo restaurar'), self.tr_text('No se pudo guardar: {error}', error=error))
            return
        self.state = state
        self.scene_drafts.clear()
        self.name.clearFocus()
        self.refresh()
        self.status.hide()
        self.pages.setCurrentIndex(0)
        self.bridge_panel.schedule()

    def show_bridge_error(self, message):
        self.bridge_error_text = self.tr_text(message)
        self.status.setText(self.bridge_error_text)
        self.status.show()

    def clear_bridge_error(self):
        if self.status.text() == getattr(self, 'bridge_error_text', None):
            self.status.hide()

    def light_name(self, index):
        selected = self.state.bridge.selected[index]
        name = next((light['name'] for light in self.state.bridge.lights if light['id'] == selected),
                    self.tr_text('Foco {number}', number=index + 1))
        return self.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, 170)

    def save_actual_dialog(self):
        if not self.actual:
            return
        dialog = QDialog(self)
        dialog.setObjectName('root')
        dialog.setWindowTitle(self.tr_text('Guardar en un ambiente'))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr_text('Elegí el ambiente que querés reemplazar y su nombre.')))
        slots = QComboBox()
        for i, scene in enumerate(self.state.schemes):
            slots.addItem(f'{i + 1} · {scene.name}', i)
        slots.setCurrentIndex(self.state.selected)
        layout.addWidget(slots)
        name = QLineEdit(self.state.current.name)
        name.setMaxLength(32)
        layout.addWidget(name)
        slots.currentIndexChanged.connect(lambda i: name.setText(self.state.schemes[i].name))
        buttons = QDialogButtonBox()
        save = buttons.addButton(self.tr_text('Guardar'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.tr_text('Cancelar'), QDialogButtonBox.ButtonRole.RejectRole)
        name.textChanged.connect(lambda text: save.setEnabled(bool(text.strip())))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.store_actual(slots.currentIndex(), name.text().strip())

    def store_actual(self, slot, name):
        if not self.actual or not name or len(name) > 32:
            return False
        previous = self.state.schemes[slot]
        snapshot = deepcopy(self.actual)
        self.state.schemes[slot] = Scheme(name, [v['color'] for v in snapshot], False,
            round(sum(v['brightness'] for v in snapshot) / 2),
            [v['brightness'] for v in snapshot], [v['on'] for v in snapshot])
        try:
            self.state.save(self.path)
        except OSError as error:
            self.state.schemes[slot] = previous
            QMessageBox.warning(self, self.tr_text('No se pudo guardar'), self.tr_text('No se pudo guardar: {error}', error=error))
            return False
        self.scene_drafts.pop(slot, None)
        self.status.setText(self.tr_text('Ambiente guardado.'))
        self.status.show()
        self.refresh()
        return True

    @property
    def editing_scene(self):
        return self.scene_drafts.get(self.state.selected, self.state.current)

    def draft_scene(self):
        return self.scene_drafts.setdefault(self.state.selected, deepcopy(self.state.current))

    def save_scene(self):
        slot = self.state.selected
        scene = deepcopy(self.editing_scene)
        scene.name = self.name.text().strip()
        if not scene.name:
            return False
        previous = self.state.schemes[slot]
        self.state.schemes[slot] = scene
        try:
            self.state.save(self.path)
        except OSError as error:
            self.state.schemes[slot] = previous
            QMessageBox.warning(self, self.tr_text('No se pudo guardar'), self.tr_text('No se pudo guardar: {error}', error=error))
            return False
        self.scene_drafts.pop(slot, None)
        self.status.setText(self.tr_text('Ambiente guardado.'))
        self.status.show()
        self.refresh()
        return True

    def receive_actual(self, lights, select=True):
        self.actual = lights
        if select:
            self.actual_view = True
        self.observed_power = [light['on'] for light in lights]
        self.state.powered = any(self.observed_power)
        self.refresh()

    def refresh(self):
        real = self.state.bridge.ready and self.bridge_panel.connected
        self.controls.setEnabled(real and not self.bridge_panel.busy)
        self.disabled_effect.setEnabled(not real)
        self.connection_notice.setVisible(not real)
        self.connection_notice.setText(self.tr_text('Sin conexión lista. Abrí Configuración (⚙) para conectar el Bridge y elegir los focos.'))
        self.badge.setText('' if real else self.tr_text('●  Sin conexión'))
        self.badge.setVisible(not real)
        self.setWindowTitle('PhiHue')
        self.save_actual_button.setEnabled(bool(self.actual))
        s = self.editing_scene
        self.save_scene_button.setEnabled(bool(s.name.strip()))
        self.scene_editor.setVisible(not self.actual_view)
        self.actual_panel.setVisible(self.actual_view)
        self.actual_button.scheme = Scheme(self.tr_text('Actual'),
            [light['color'] for light in self.actual] if self.actual else ['#555555'] * 2)
        self.actual_button.actual_lights = self.actual
        self.actual_button.setChecked(self.actual_view)
        self.actual_button.setAccessibleName(self.tr_text('Actual'))
        self.actual_button.update()
        for i, label in enumerate(self.actual_labels):
            if self.actual:
                light = self.actual[i]
                self.actual_sliders[i].blockSignals(True)
                self.actual_sliders[i].setValue(round(light['brightness']))
                self.actual_sliders[i].blockSignals(False)
                color = display_color(light['color'], light['brightness'], light['on'])
                ink = '#10141d' if color.lightnessF() > .55 else '#ffffff'
                label.setStyleSheet(f'background: {color.name()}; color: {ink}; border-radius: 12px; padding: 12px;')
                label.setText(self.light_name(i) + '  ·  ' +
                    self.tr_text('Encendido' if light['on'] else 'Apagado') +
                    f"  ·  {light['brightness']:.0f}%  ·  ≈ {light['color'].upper()}")
            else:
                label.setText(self.tr_text('Esperando lectura del Bridge…'))
        for i, button in enumerate(self.buttons):
            button.scheme = self.scene_drafts.get(i, self.state.schemes[i])
            button.powered = self.state.powered
            button.setAccessibleName(button.scheme.name)
            button.setToolTip(button.scheme.name)
            button.update()
            button.setChecked(not self.actual_view and i == self.state.selected)
        if not self.name.hasFocus():
            self.name.setText(s.name)
        self.brightness.blockSignals(True)
        self.brightness.setValue(s.brightness)
        self.brightness.blockSignals(False)
        for i, button in enumerate(self.color_buttons):
            observed = getattr(self, 'observed_power', None)
            c = display_color(s.colors[i], s.brightnesses[i] if s.brightnesses else s.brightness, observed[i] if observed else s.powers[i] if s.powers else self.state.powered)
            ink = '#10141d' if c.lightnessF() > 0.55 else '#ffffff'
            button.setText(self.light_name(i) + f'    ·    {s.colors[i].upper()}    ↗')
            button.setStyleSheet(f'background: {c.name()}; color: {ink};')
        self.brightness_label.setText(
            self.tr_text('Brillos · {first}% / {second}%', first=round(s.brightnesses[0]), second=round(s.brightnesses[1]))
            if s.brightnesses and s.brightnesses[0] != s.brightnesses[1] else
            self.tr_text('Brillo común · {value}%', value=s.brightness))
        self.power.blockSignals(True)
        self.power.setChecked(self.state.powered)
        self.power.blockSignals(False)
        self.power.setToolTip(self.tr_text('Apagar' if self.state.powered else 'Encender'))
        self.ensurePolished()
        self.controls.layout().invalidate()
        self.controls.layout().activate()
        self.controls.updateGeometry()
        self.main_page.layout().invalidate()
        self.fit_window()

    def changed(self, control=True):
        if control:
            self.observed_power = None
        self.refresh()
        try:
            self.state.save(self.path)
            if self.editing_scene != self.state.current:
                self.status.setText(self.tr_text('Cambios sin guardar. Pulsá el disquete para guardar el ambiente.'))
                self.status.show()
            else:
                self.status.hide()
        except OSError as error:
            self.status.setText(self.tr_text('No se pudo guardar: {error}', error=error))
            self.status.show()
        if control:
            self.bridge_panel.schedule()

    def select(self, index):
        self.actual_view = False
        self.state.selected = index
        if self.editing_scene.powers is not None:
            self.state.powered = any(self.editing_scene.powers)
        self.changed()

    def rename(self, text=None):
        name = self.name.text().strip()
        self.draft_scene().name = name
        self.changed(control=False)

    def copy_color(self, source):
        self.draft_scene().set_color(1 - source, self.editing_scene.colors[source])
        self.changed()

    def edit_actual(self, index, **values):
        if not self.actual or not self.actual_view:
            return
        self.actual[index].update(values)
        if values.get('color') == '#000000':
            self.actual[index]['on'] = False
            self.state.powered = any(light['on'] for light in self.actual)
        self.refresh()
        self.bridge_panel.schedule_actual(index, values)

    def pick_actual_color(self, index):
        if not self.actual:
            return
        dialog = QColorDialog(QColor(self.actual[index]['color']), self)
        dialog.setWindowTitle(self.tr_text('Color del foco {number}', number=index + 1))
        dialog.setOption(QColorDialog.ColorDialogOption.NoButtons)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dialog.currentColorChanged.connect(lambda color: self.edit_actual(index, color=color.name()))
        dialog.exec()

    def pick_color(self, index):
        dialog = QColorDialog(QColor(self.editing_scene.colors[index]), self)
        dialog.setWindowTitle(self.tr_text('Color del foco {number}', number=index + 1))
        dialog.setOption(QColorDialog.ColorDialogOption.NoButtons)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        def apply_color(color):
            self.draft_scene().set_color(index, color.name())
            self.changed()
        dialog.currentColorChanged.connect(apply_color)
        dialog.exec()

    def adjust_brightness(self, value):
        self.draft_scene().brightnesses = None
        self.draft_scene().brightness = value
        self.changed()

    def toggle_power(self):
        if self.actual_view:
            self.bridge_panel.toggle_actual_power()
            self.refresh()
            return
        self.draft_scene().powers = None
        self.state.powered = not self.state.powered
        self.changed()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('PhiHue')
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets' / 'icon.png')))
    app.setStyle('Fusion')
    window = Window()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
