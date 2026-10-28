import sys
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QFont, QPen
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QSlider, QColorDialog, QFrame)
from .model import State

ROOT = Path(__file__).resolve().parent.parent

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
            p.setBrush(display_color(color, self.scheme.brightness, self.powered))
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
    QLineEdit:focus { border-color: #b9a0f5; }
    QPushButton { border-radius: 12px; padding: 12px; }
    QPushButton:focus { border: 1px solid #d3c4ff; }
    QSlider::groove:horizontal { height: 6px; background: #3b3946; border-radius: 3px; }
    QSlider::sub-page:horizontal { background: #b9a0f5; border-radius: 3px; }
    QSlider::handle:horizontal { width: 18px; margin: -6px 0; background: #eee5ff; border-radius: 9px; }
"""

class Window(QMainWindow):
    def __init__(self, path=ROOT / 'data' / 'state.json'):
        super().__init__()
        self.path = path
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
        self.setWindowTitle('PhiHue · Simulador')
        self.resize(860, 650)
        self.setMinimumWidth(810)
        self.setStyleSheet(STYLE)
        container = QWidget()
        container.setObjectName('root')
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QLabel('PhiHue')
        title.setObjectName('brand')
        title.setFont(QFont('Helvetica', 26, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        badge = QLabel('●  Simulación local')
        badge.setObjectName('muted')
        header.addWidget(badge)
        layout.addLayout(header)
        caption = QLabel('TUS AMBIENTES')
        caption.setObjectName('eyebrow')
        layout.addWidget(caption)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.buttons = []
        for i in range(5):
            button = SchemeCard(i + 1)
            button.clicked.connect(lambda checked=False, index=i: self.select(index))
            row.addWidget(button, 1)
            self.buttons.append(button)
        layout.addLayout(row)
        panel = QFrame()
        panel.setObjectName('panel')
        editor = QVBoxLayout(panel)
        editor.setContentsMargins(24, 22, 24, 22)
        editor.setSpacing(20)
        name_row = QHBoxLayout()
        label = QLabel('Personalizá tu ambiente')
        label.setObjectName('sectionTitle')
        label.setFont(QFont('Helvetica', 15, QFont.Weight.Medium))
        name_row.addWidget(label)
        name_row.addStretch()
        self.name = QLineEdit()
        self.name.setAccessibleName('Nombre del esquema')
        self.name.setMaxLength(32)
        self.name.setFixedWidth(230)
        self.name.textEdited.connect(self.rename)
        name_row.addWidget(self.name)
        editor.addLayout(name_row)
        colors = QHBoxLayout()
        colors.setSpacing(14)
        self.color_buttons = []
        for i in range(2):
            button = QPushButton()
            button.setMinimumHeight(62)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, index=i: self.pick_color(index))
            colors.addWidget(button)
            self.color_buttons.append(button)
        editor.addLayout(colors)
        copy_row = QHBoxLayout()
        copy_row.addStretch()
        for source, label in [(0, '1 → 2'), (1, '1 ← 2')]:
            button = QPushButton(label)
            button.setStyleSheet('background: #30303b; color: #ddd1f6; padding: 8px 18px;')
            button.setToolTip(f'Copiar color del foco {source + 1} al foco {2 - source}')
            button.setAccessibleName(button.toolTip())
            button.clicked.connect(lambda checked=False, index=source: self.copy_color(index))
            copy_row.addWidget(button)
        copy_row.addStretch()
        editor.addLayout(copy_row)
        brightness_row = QHBoxLayout()
        self.brightness_label = QLabel()
        self.brightness_label.setMinimumWidth(155)
        brightness_row.addWidget(self.brightness_label)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setAccessibleName('Brillo común de los dos focos')
        self.brightness.valueChanged.connect(self.adjust_brightness)
        brightness_row.addWidget(self.brightness)
        editor.addLayout(brightness_row)
        layout.addWidget(panel)
        power_row = QHBoxLayout()
        power_row.addStretch()
        self.power = PowerButton()
        self.power.toggled.connect(self.toggle_power)
        power_row.addWidget(self.power)
        power_row.addStretch()
        layout.addLayout(power_row)
        layout.addStretch()
        self.status = QLabel(warning)
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        self.status.setVisible(bool(warning))
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        s = self.state.current
        for i, button in enumerate(self.buttons):
            button.scheme = self.state.schemes[i]
            button.powered = self.state.powered
            button.setAccessibleName(button.scheme.name)
            button.setToolTip(button.scheme.name)
            button.update()
            button.setChecked(i == self.state.selected)
        if not self.name.hasFocus():
            self.name.setText(s.name)
        self.brightness.blockSignals(True)
        self.brightness.setValue(s.brightness)
        self.brightness.blockSignals(False)
        for i, button in enumerate(self.color_buttons):
            c = display_color(s.colors[i], s.brightness, self.state.powered)
            ink = '#10141d' if c.lightnessF() > 0.55 else '#ffffff'
            button.setText(f'Foco {i+1}    ·    {s.colors[i].upper()}    ↗')
            button.setStyleSheet(f'background: {c.name()}; color: {ink};')
        self.brightness_label.setText(f'Brillo común · {s.brightness}%')
        self.power.blockSignals(True)
        self.power.setChecked(self.state.powered)
        self.power.blockSignals(False)
        self.power.setToolTip('Apagar' if self.state.powered else 'Encender')

    def changed(self):
        self.refresh()
        try:
            self.state.save(self.path)
            self.status.hide()
        except OSError as error:
            self.status.setText(f'No se pudo guardar: {error}')
            self.status.show()

    def select(self, index):
        self.state.selected = index
        self.changed()

    def rename(self, text=None):
        name = self.name.text().strip()
        if name:
            self.state.current.name = name
        self.changed()

    def copy_color(self, source):
        self.state.current.set_color(1 - source, self.state.current.colors[source])
        self.changed()

    def pick_color(self, index):
        dialog = QColorDialog(QColor(self.state.current.colors[index]), self)
        dialog.setWindowTitle(f'Color del foco {index + 1}')
        dialog.setOption(QColorDialog.ColorDialogOption.NoButtons)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        def apply_color(color):
            self.state.current.set_color(index, color.name())
            self.changed()
        dialog.currentColorChanged.connect(apply_color)
        dialog.exec()

    def adjust_brightness(self, value):
        self.state.current.brightness = value
        self.changed()

    def toggle_power(self):
        self.state.powered = not self.state.powered
        self.changed()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
