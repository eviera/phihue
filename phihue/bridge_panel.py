"""Bridge setup and serialized background network operations."""
from copy import deepcopy

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QMessageBox

from .hue import HueClient, HueError, discover, validate_address, rgb_to_xy
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
        self.connected = False
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
        window.bind(description.setText, '1. Buscá el Bridge en tu red o ingresá su IP')
        layout.addWidget(description)
        row = QHBoxLayout()
        self.address = QLineEdit(self.settings.address)
        window.bind(self.address.setPlaceholderText, 'IP del Bridge (ej. 192.168.1.20)')
        window.bind(self.address.setAccessibleName, 'IP del Bridge')
        row.addWidget(self.address, 1)
        self.search = self.button(row, 'Buscar Bridge', self.search_bridges)
        layout.addLayout(row)
        step = QLabel()
        window.bind(step.setText, '2. Presioná el botón del Bridge y luego Vincular')
        layout.addWidget(step)
        row = QHBoxLayout()
        self.pair_button = self.button(row, 'Vincular', self.pair)
        layout.addLayout(row)
        self.bridges = QComboBox()
        window.bind(self.bridges.setAccessibleName, 'Bridges encontrados')
        self.bridges.activated.connect(lambda index: self.address.setText(self.bridges.itemData(index)))
        self.bridges.hide()
        layout.addWidget(self.bridges)
        row = QHBoxLayout()
        step = QLabel()
        window.bind(step.setText, '3. Elegí los dos focos que vas a controlar')
        layout.addWidget(step)
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
        self.accept_button = self.button(row, 'Aceptar y volver', self.accept_settings)
        self.disconnect_button = self.button(row, 'Desvincular Bridge', self.disconnect_bridge)
        row.addStretch()
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        layout.addWidget(self.status)
        self.address.textChanged.connect(self.enable_controls)
        self.retranslate()
        if self.settings.key:
            QTimer.singleShot(0, self.load_lights)

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
        for index, selector in enumerate(self.selectors):
            selector.blockSignals(True)
            selector.clear()
            selector.addItem(self.window.tr_text('Elegí un foco'), '')
            for light in self.settings.lights:
                selector.addItem(light['name'], light['id'])
            selector.setCurrentIndex(max(0, selector.findData(self.settings.selected[index])))
            selector.blockSignals(False)
        self.tell(self.message or ('Bridge vinculado.' if self.settings.key else 'Completá los tres pasos para habilitar los controles.'))
        self.enable_controls()

    def enable_controls(self):
        for widget in [self.address, self.search, self.pair_button, self.bridges, *self.selectors]:
            widget.setEnabled(not self.busy)
        self.accept_button.setEnabled(not self.busy and self.connected and self.settings.ready)
        self.reload.setEnabled(not self.busy and bool(self.settings.key))
        self.disconnect_button.setEnabled(not self.busy and bool(self.settings.key))
        self.pair_button.setEnabled(not self.busy and bool(self.address.text().strip()))
        for selector in self.selectors:
            selector.setEnabled(not self.busy and self.connected and bool(self.settings.lights))
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
        self.mode_changed.emit()
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
            if not error.startswith('El Bridge está conectado, pero un foco no responde.'):
                self.connected = False
            self.mode_changed.emit()
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
        self.mode_changed.emit()

    def accept_settings(self):
        if self.busy or not self.connected or not self.settings.ready:
            return
        if self.save(deepcopy(self.settings)):
            self.return_to_controls(saved=True)

    def return_to_controls(self, saved=False):
        if self.busy:
            return
        if not self.settings.ready:
            self.window.pages.setCurrentIndex(0)
            return
        self.timer.stop()
        self.pending = None
        client = self.client()
        ids = list(self.settings.selected)

        def received(states):
            self.connected = True
            self.window.receive_actual(states)
            powers = [light['on'] for light in states]
            self.window.refresh()
            self.window.pages.setCurrentIndex(0)
            message = ('Un foco está encendido y el otro apagado. El botón apagará ambos.'
                       if powers[0] != powers[1] else
                       'Configuración guardada. Estado de los focos actualizado.' if saved else
                       'Estado de los focos actualizado.')
            self.window.status.setText(self.window.tr_text(message))
            self.window.status.show()
            self.tell(message)

        self.start(lambda: client.light_states(ids), received)

    def disconnect_bridge(self):
        if self.busy or not self.settings.key:
            return
        # Prevent a queued light update from starting inside the modal dialog.
        self.timer.stop()
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.window.tr_text('Desvincular Bridge'))
        dialog.setText(self.window.tr_text('¿Querés desvincular el Bridge?'))
        dialog.setInformativeText(self.window.tr_text('Se borrará la conexión y los controles quedarán deshabilitados. Tus ambientes e idioma se conservan.'))
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
        self.connected = False
        self.mode_changed.emit()
        self.address.clear()
        self.bridges.clear()
        self.bridges.hide()
        self.window.clear_bridge_error()
        self.tell('Bridge desvinculado. Conectalo para habilitar los controles.')

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
                self.tell('No se encontró un Bridge. Revisá la red o ingresá su IP.')
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
        selected = list(self.settings.selected)

        def fetch():
            lights = client.lights()
            ids = {light['id'] for light in lights}
            states = client.light_states(selected) if all(value in ids for value in selected) else None
            return lights, states

        def loaded(result):
            lights, states = result
            if states is not None:
                self.window.receive_actual(states)
            self.connected = True
            candidate = deepcopy(self.settings)
            candidate.lights = lights
            ids = {light['id'] for light in lights}
            candidate.selected = [value if value in ids else '' for value in candidate.selected]
            if not candidate.ready:
                candidate.mode = 'simulation'
            if self.save(candidate):
                self.tell('Focos guardados. Elegí Aceptar y volver para continuar.' if candidate.ready else 'Elegí dos focos distintos.' if len(lights) >= 2 else 'Se necesitan dos focos con capacidad de color. Revisá tus focos en la app Hue.')
        self.start(fetch, loaded)

    def choose_lights(self):
        candidate = deepcopy(self.settings)
        candidate.selected = [selector.currentData() or '' for selector in self.selectors]
        if candidate.selected[0] and candidate.selected[0] == candidate.selected[1]:
            self.tell('Elegí dos focos distintos.')
            self.retranslate()
            return
        candidate.mode = 'real' if candidate.ready else 'simulation'
        self.pending = None
        if self.save(candidate):
            self.tell('Focos guardados. Elegí Aceptar y volver para continuar.' if candidate.ready else 'Elegí dos focos distintos.')

    def toggle_actual_power(self):
        if self.busy or not self.connected or not self.settings.ready:
            return
        self.timer.stop()
        self.pending = None
        client = self.client()
        ids = list(self.settings.selected)
        powered = not self.window.state.powered
        def apply_and_read():
            client.set_power(ids, powered)
            return client.light_states(ids)
        self.start(apply_and_read, self.window.receive_actual, controlling=True)

    def schedule_actual(self, index, values):
        if not self.connected or not self.settings.ready:
            return
        if not isinstance(self.pending, dict):
            self.pending = {}
        self.pending.setdefault(index, {}).update(values)
        self.timer.start()

    def schedule(self):
        if not self.connected or not self.settings.ready:
            return
        self.pending = True
        self.timer.start()

    def flush(self):
        if self.busy or not self.pending:
            return
        if not self.connected or not self.settings.ready:
            self.pending = None
            return
        if isinstance(self.pending, dict):
            edits = deepcopy(self.pending)
            self.pending = None
            client = self.client()
            ids = list(self.settings.selected)
            def apply_edits():
                for index, values in edits.items():
                    payload = {}
                    if 'color' in values:
                        x, y = rgb_to_xy(values['color'])
                        if values['color'].lower() == '#000000':
                            payload['on'] = {'on': False}
                        else:
                            payload['color'] = {'xy': {'x': x, 'y': y}}
                    if 'brightness' in values:
                        payload['dimming'] = {'brightness': float(values['brightness'])}
                    client.request('PUT', '/clip/v2/resource/light/' + ids[index], payload)
            self.start(apply_edits, lambda _: self.tell('Cambios aplicados a las luces.'), controlling=True)
            return
        state = self.window.state
        client = self.client()
        scene = self.window.editing_scene
        ids, colors = list(self.settings.selected), list(scene.colors)
        brightness = deepcopy(scene.brightnesses) or scene.brightness
        powered = deepcopy(scene.powers) if scene.powers is not None else state.powered
        self.pending = None
        def apply_and_read():
            client.apply(ids, colors, brightness, powered)
            return client.light_states(ids)

        def applied(lights):
            self.window.receive_actual(lights, select=False)
            self.tell('Ambiente aplicado.')

        self.start(apply_and_read, applied, controlling=True)
