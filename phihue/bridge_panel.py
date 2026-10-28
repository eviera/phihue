"""Bridge setup and serialized background network operations."""
from copy import deepcopy

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QMessageBox

from .hue import HueClient, HueError, discover, validate_address
from .model import BridgeSettings


class JobSignals(QObject):
    finished = Signal(object, object)


class Job(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = JobSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.operation(), None)
        except HueError as error:
            self.signals.finished.emit(None, str(error))
        except Exception:
            # Never expose API credentials through exception strings.
            self.signals.finished.emit(None, 'No se pudo completar la operación del Bridge.')


class BridgePanel(QFrame):
    mode_changed = Signal()
    control_error = Signal(str)
    control_success = Signal()

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName('panel')
        self.busy = False
        self.job = None
        self.pending = None
        self.message = ''
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.flush)
        self.pool = QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel('Hue Bridge')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        description = QLabel()
        description.setWordWrap(True)
        description.setObjectName('muted')
        window.bind(description.setText, 'En casa, buscá el Bridge o ingresá su IP. Presioná su botón físico y elegí Vincular. Después seleccioná dos focos de color.')
        layout.addWidget(description)
        row = QHBoxLayout()
        self.address = QLineEdit(self.settings.address)
        window.bind(self.address.setPlaceholderText, 'IP del Bridge (ej. 192.168.1.20)')
        window.bind(self.address.setAccessibleName, 'IP del Bridge')
        row.addWidget(self.address, 1)
        self.search = self.button(row, 'Buscar Bridge', self.search_bridges)
        self.pair_button = self.button(row, 'Vincular', self.pair)
        layout.addLayout(row)
        self.bridges = QComboBox()
        window.bind(self.bridges.setAccessibleName, 'Bridges encontrados')
        self.bridges.activated.connect(lambda index: self.address.setText(self.bridges.itemData(index)))
        self.bridges.hide()
        layout.addWidget(self.bridges)
        row = QHBoxLayout()
        self.selectors = []
        for number in (1, 2):
            label = QLabel()
            window.bind(label.setText, 'Foco {number}', number=number)
            row.addWidget(label)
            selector = QComboBox()
            selector.setMinimumWidth(140)
            window.bind(selector.setAccessibleName, 'Foco {number}', number=number)
            selector.currentIndexChanged.connect(self.choose_lights)
            self.selectors.append(selector)
            row.addWidget(selector, 1)
        self.reload = self.button(row, 'Actualizar focos', self.load_lights)
        layout.addLayout(row)
        row = QHBoxLayout()
        label = QLabel()
        window.bind(label.setText, 'Modo')
        row.addWidget(label)
        self.mode = QComboBox()
        self.mode.addItem('', 'simulation')
        self.mode.addItem('', 'real')
        window.bind(self.mode.setAccessibleName, 'Modo')
        self.mode.currentIndexChanged.connect(self.change_mode)
        row.addWidget(self.mode, 1)
        self.retry = self.button(row, 'Aplicar ambiente', self.schedule)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.disconnect_button = self.button(row, 'Desvincular Bridge', self.disconnect_bridge)
        row.addStretch()
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        layout.addWidget(self.status)
        self.retranslate()

    @property
    def settings(self):
        return self.window.state.bridge

    def button(self, layout, text, callback):
        button = QPushButton()
        button.setStyleSheet('QPushButton { background: #30303b; color: #ddd1f6; } '
                            'QPushButton:disabled { background: #25252c; color: #706b7a; }')
        self.window.bind(button.setText, text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def tell(self, message):
        self.message = message
        self.status.setText(self.window.tr_text(message))

    def retranslate(self):
        self.mode.blockSignals(True)
        self.mode.setItemText(0, self.window.tr_text('Simulación'))
        self.mode.setItemText(1, self.window.tr_text('Focos reales'))
        self.mode.setCurrentIndex(1 if self.settings.mode == 'real' else 0)
        self.mode.blockSignals(False)
        for index, selector in enumerate(self.selectors):
            selector.blockSignals(True)
            selector.clear()
            selector.addItem(self.window.tr_text('Elegí un foco'), '')
            for light in self.settings.lights:
                selector.addItem(light['name'], light['id'])
            selector.setCurrentIndex(max(0, selector.findData(self.settings.selected[index])))
            selector.blockSignals(False)
        self.tell(self.message or ('Bridge vinculado.' if self.settings.key else 'Simulación disponible. Vinculá el Bridge cuando estés en casa.'))
        self.enable_controls()

    def enable_controls(self):
        for widget in [self.address, self.search, self.pair_button, self.bridges, *self.selectors]:
            widget.setEnabled(not self.busy)
        self.reload.setEnabled(not self.busy and bool(self.settings.key))
        self.disconnect_button.setEnabled(not self.busy and bool(self.settings.key))
        self.retry.setEnabled(not self.busy and self.settings.ready and self.settings.mode == 'real')
        # Simulation always remains selectable, even during a network request.

    def save(self, candidate):
        old = self.window.state.bridge
        self.window.state.bridge = candidate
        try:
            self.window.state.save(self.window.path)
        except OSError:
            self.window.state.bridge = old
            self.tell('No se pudo guardar la configuración del Bridge.')
            self.retranslate()
            return False
        self.retranslate()
        self.mode_changed.emit()
        return True

    def start(self, operation, success, controlling=False):
        if self.busy:
            return
        self.busy = True
        self.enable_controls()
        self.tell('Conectando…')
        self.job = Job(operation)
        self._success = success
        self._controlling = controlling
        self.job.signals.finished.connect(self.finished)
        self.pool.start(self.job)

    def finished(self, result, error):
        self.busy = False
        self.job = None
        if error:
            self.tell(error)
            if self._controlling:
                self.pending = None
                self.timer.stop()
                self.control_error.emit(error)
        else:
            if self._controlling:
                self.control_success.emit()
            self._success(result)
        self.enable_controls()
        if self.pending:
            self.timer.start()

    def disconnect_bridge(self):
        if self.busy or not self.settings.key:
            return
        # Prevent a queued light update from starting inside the modal dialog.
        self.timer.stop()
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.window.tr_text('Desvincular Bridge'))
        dialog.setText(self.window.tr_text('¿Querés desvincular el Bridge?'))
        dialog.setInformativeText(self.window.tr_text('Se borrará la conexión guardada en esta app y volverás a simulación. Tus ambientes e idioma se conservan. No necesitás estar en casa.'))
        disconnect = dialog.addButton(self.window.tr_text('Desvincular'), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(self.window.tr_text('Cancelar'), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        if dialog.clickedButton() != disconnect or not self.save(BridgeSettings()):
            if self.pending:
                self.timer.start()
            return
        self.pending = None
        self.address.clear()
        self.bridges.clear()
        self.bridges.hide()
        self.window.clear_bridge_error()
        self.tell('Bridge desvinculado. Podés seguir usando la simulación.')

    def search_bridges(self):
        def found(addresses):
            self.bridges.clear()
            for address in addresses:
                self.bridges.addItem(address, address)
            self.bridges.setVisible(len(addresses) > 1)
            if addresses:
                self.address.setText(addresses[0])
                self.tell('Bridge encontrado. Presioná su botón físico y elegí Vincular.')
            else:
                self.tell('No se encontró un Bridge. Podés ingresar su IP o seguir en simulación.')
        self.start(discover, found)

    def pair(self):
        try:
            address = validate_address(self.address.text())
        except HueError as error:
            self.tell(str(error))
            return
        # Explicit re-pairing is the only operation allowed to trust a new cert.
        client = HueClient(address)
        def paired(credentials):
            key, fingerprint = credentials
            candidate = BridgeSettings(address=address, key=key, fingerprint=fingerprint)
            if self.save(candidate):
                self.pending = None
                self.tell('Bridge vinculado. Actualizá los focos para elegirlos.')
                self.load_lights()
        self.start(client.pair, paired)

    def client(self):
        return HueClient(self.settings.address, self.settings.key, self.settings.fingerprint)

    def load_lights(self):
        try:
            client = self.client()
        except HueError as error:
            self.tell(str(error))
            return
        def loaded(lights):
            candidate = deepcopy(self.settings)
            candidate.lights = lights
            ids = {light['id'] for light in lights}
            candidate.selected = [value if value in ids else '' for value in candidate.selected]
            if not candidate.ready:
                candidate.mode = 'simulation'
            if self.save(candidate):
                self.tell('Elegí dos focos distintos.' if len(lights) >= 2 else 'Se necesitan dos focos con capacidad de color. Revisá tus focos en la app Hue.')
        self.start(client.lights, loaded)

    def choose_lights(self):
        candidate = deepcopy(self.settings)
        candidate.selected = [selector.currentData() or '' for selector in self.selectors]
        if candidate.selected[0] and candidate.selected[0] == candidate.selected[1]:
            self.tell('Elegí dos focos distintos.')
            self.retranslate()
            return
        candidate.mode = 'simulation'
        self.pending = None
        if self.save(candidate):
            self.tell('Focos guardados. Activá Focos reales para controlarlos.' if candidate.ready else 'Elegí dos focos distintos.')

    def change_mode(self):
        candidate = deepcopy(self.settings)
        candidate.mode = self.mode.currentData()
        if candidate.mode == 'real' and not candidate.ready:
            self.tell('Primero vinculá el Bridge y elegí dos focos distintos.')
            self.retranslate()
            return
        if self.save(candidate):
            if candidate.mode == 'real':
                self.schedule()
            else:
                self.pending = None
                self.timer.stop()
                self.tell('Simulación activa. No se envían nuevos cambios al Bridge.')

    def schedule(self):
        if self.settings.mode != 'real' or not self.settings.ready:
            return
        self.pending = True
        self.timer.start()

    def flush(self):
        if self.busy or not self.pending:
            return
        if self.settings.mode != 'real' or not self.settings.ready:
            self.pending = None
            return
        state = self.window.state
        client = self.client()
        ids, colors = list(self.settings.selected), list(state.current.colors)
        brightness, powered = state.current.brightness, state.powered
        self.pending = None
        self.start(lambda: client.apply(ids, colors, brightness, powered),
                   lambda _: self.tell('Ambiente aplicado.'), controlling=True)
