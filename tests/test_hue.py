from copy import deepcopy
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from phihue.hue import HueClient, HueError, discover, rgb_to_xy, validate_address
from phihue.model import State, BridgeSettings
from phihue.__main__ import Window

IDS = ['11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222']
LIGHTS = [{'id': value, 'name': name} for value, name in zip(IDS, ['Desk', 'Wall'])]
PIN = hashlib.sha256(b'certificate').hexdigest()


class ClientTests(unittest.TestCase):
    def connection(self, data, status=200):
        connection = MagicMock()
        connection.sock.getpeercert.return_value = b'certificate'
        connection.getresponse.return_value.status = status
        connection.getresponse.return_value.read.return_value = json.dumps(data).encode()
        return connection

    def test_pair_button_then_success(self):
        conn = self.connection([{'error': {'type': 101}}])
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(HueError, 'botón físico'):
                HueClient('192.168.1.20').pair()
        conn = self.connection([{'success': {'username': 'test-key'}}])
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            self.assertEqual(HueClient('192.168.1.20').pair(), ('test-key', PIN))
        self.assertEqual(conn.request.call_args.args[:2], ('POST', '/api'))
        conn.close.assert_called_once()

    def test_certificate_mismatch_never_sends_credentials(self):
        conn = self.connection({})
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(HueError, 'certificado'):
                HueClient('192.168.1.20', 'secret', '0' * 64).lights()
        conn.request.assert_not_called()

    def test_api_errors_and_timeout(self):
        for data, status in [({'errors': [{'description': 'bad'}], 'data': []}, 200), ({}, 403), ({}, 200)]:
            with patch('phihue.hue.http.client.HTTPSConnection', return_value=self.connection(data, status)):
                with self.assertRaises(HueError):
                    HueClient('192.168.1.20', 'key', PIN).lights()
        conn = self.connection({})
        conn.connect.side_effect = TimeoutError()
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(HueError, 'misma red'):
                HueClient('192.168.1.20').pair()

    def test_lights_filter_and_auth_header(self):
        data = {'errors': [], 'data': [
            {'id': IDS[0], 'metadata': {'name': 'Desk'}, 'color': {}, 'dimming': {}},
            {'id': IDS[1], 'metadata': {'name': 'White'}, 'dimming': {}}]}
        conn = self.connection(data)
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            self.assertEqual(HueClient('192.168.1.20', 'key', PIN).lights(), LIGHTS[:1])
        self.assertEqual(conn.request.call_args.args[3]['hue-application-key'], 'key')

    def test_control_payloads_and_black_or_zero_are_off(self):
        client = HueClient('192.168.1.20', 'key', PIN)
        with patch.object(client, 'request') as request:
            client.apply(IDS, ['#ff0000', '#000000'], 42, True)
            first, second = [call.args[2] for call in request.call_args_list]
            self.assertTrue(first['on']['on'])
            self.assertEqual(first['dimming']['brightness'], 42)
            self.assertAlmostEqual(first['color']['xy']['x'], .7006, places=3)
            self.assertEqual(second, {'on': {'on': False}})
            request.reset_mock()
            client.apply(IDS, ['#ffffff'] * 2, 0, True)
            self.assertTrue(all(call.args[2] == {'on': {'on': False}} for call in request.call_args_list))
        self.assertEqual(rgb_to_xy('#000000'), (0, 0))

    def test_discovery_empty_and_address_validation(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'[]'
        with patch('phihue.hue.urlopen', return_value=response):
            self.assertEqual(discover(), [])
        for address in ('https://example.com', '8.8.8.8', '127.0.0.1', '::1', '0.0.0.0'):
            with self.assertRaises(HueError):
                validate_address(address)

    def test_settings_roundtrip_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            state = State(bridge=BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real'))
            state.save(path)
            self.assertEqual(State.load(path), state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("'key'", repr(state.bridge))
            self.assertEqual(BridgeSettings.from_dict({'selected': None}).mode, 'simulation')


class BridgeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.json'
        self.window = Window(self.path)
        self.panel = self.window.bridge_panel
        self.addCleanup(self.window.close)
        self.addCleanup(self.app.removeTranslator, self.window.qt_translator)

    def wait_idle(self):
        until = time.monotonic() + 3
        while self.panel.busy and time.monotonic() < until:
            QTest.qWait(10)
        self.assertFalse(self.panel.busy)

    def test_pair_select_enable_and_apply_in_background(self):
        with patch.object(HueClient, 'pair', return_value=('key', PIN)), patch.object(HueClient, 'lights', return_value=LIGHTS), patch.object(HueClient, 'apply') as apply:
            self.panel.address.setText('192.168.1.20')
            self.panel.pair_button.click()
            self.wait_idle()
            self.assertEqual(self.window.state.bridge.lights, LIGHTS)
            self.panel.selectors[0].setCurrentIndex(1)
            self.panel.selectors[1].setCurrentIndex(1)
            self.assertEqual(self.window.state.bridge.selected, [IDS[0], ''])
            self.panel.selectors[1].setCurrentIndex(2)
            self.assertTrue(self.window.state.bridge.ready)
            apply.assert_not_called()
            self.panel.mode.setCurrentIndex(1)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[0], IDS)
            self.assertEqual(State.load(self.path).bridge.mode, 'real')
            self.assertIn('Focos reales', self.window.badge.text())
            self.window.adjust_brightness(10)
            self.window.adjust_brightness(30)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[2], 30)
            self.assertEqual(apply.call_count, 2)
            self.window.adjust_brightness(50)
            self.panel.mode.setCurrentIndex(0)
            self.panel.flush()
            self.assertEqual(apply.call_count, 2)

    def test_offline_error_and_no_real_mode_without_pairing(self):
        self.panel.mode.setCurrentIndex(1)
        self.assertEqual(self.window.state.bridge.mode, 'simulation')
        with patch('phihue.bridge_panel.discover', side_effect=HueError('No se pudo buscar el Bridge. Podés ingresar su IP manualmente.')):
            self.panel.search.click()
            self.wait_idle()
        self.assertIn('No se pudo buscar', self.panel.status.text())
        self.assertTrue(self.panel.pair_button.isEnabled())
        with patch.object(HueClient, 'apply') as apply:
            self.window.adjust_brightness(40)
            self.panel.flush()
            apply.assert_not_called()

    def test_no_requests_on_reopen(self):
        state = State(bridge=BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real'))
        state.save(self.path)
        with patch.object(HueClient, 'request') as request:
            other = Window(self.path)
            QTest.qWait(20)
            request.assert_not_called()
            other.close()
            self.app.removeTranslator(other.qt_translator)

    def test_control_failure_keeps_configuration_and_can_retry(self):
        self.window.state.bridge = BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real')
        self.window.state.save(self.path)
        self.panel.retranslate()
        with patch.object(HueClient, 'apply', side_effect=HueError('No se pudo contactar al Bridge. Revisá que estés en la misma red.')):
            self.panel.schedule()
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
        self.assertIn('No se pudo contactar', self.window.status.text())
        self.assertEqual(State.load(self.path).bridge.selected, IDS)
        with patch.object(HueClient, 'apply') as apply:
            self.panel.retry.click()
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            apply.assert_called_once()
            self.assertTrue(self.window.status.isHidden())

    def test_reset_preserves_pairing_and_language(self):
        bridge = BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS)
        self.window.state.bridge = bridge
        self.window.state.language = 'en'
        self.window.state.current.name = 'Custom'
        def confirm(dialog):
            next(button for button in dialog.buttons()
                 if dialog.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole).click()
            return 0
        with patch.object(QMessageBox, 'exec', confirm):
            self.window.reset_settings()
        saved = State.load(self.path)
        self.assertEqual(saved.bridge, bridge)
        self.assertEqual(saved.language, 'en')
        self.assertEqual(saved.current.name, 'Lectura')

    def prepare_unpair(self):
        self.window.state.bridge = BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real')
        self.window.state.language = 'en'
        self.window.state.current.name = 'Custom'
        self.window.state.save(self.path)
        self.window.apply_language()
        self.panel.schedule()

    def dialog_choice(self, role):
        def choose(dialog):
            self.assertFalse(self.panel.timer.isActive())
            self.assertEqual(dialog.text(), 'Unpair this Bridge?')
            next(button for button in dialog.buttons() if dialog.buttonRole(button) == role).click()
            return 0
        return choose

    def test_unpair_offline_clears_credentials_and_pending_preserves_scenes(self):
        self.prepare_unpair()
        before = deepcopy(self.window.state.schemes)
        with patch.object(QMessageBox, 'exec', self.dialog_choice(QMessageBox.ButtonRole.DestructiveRole)), patch.object(HueClient, 'request') as request:
            self.panel.disconnect_button.click()
            self.panel.flush()
            request.assert_not_called()
        saved = State.load(self.path)
        self.assertEqual(saved.bridge, BridgeSettings())
        self.assertEqual(saved.schemes, before)
        self.assertEqual(saved.language, 'en')
        self.assertFalse(self.panel.pending)
        self.assertFalse(self.panel.timer.isActive())
        self.assertEqual(self.panel.address.text(), '')
        self.assertFalse(self.panel.disconnect_button.isEnabled())
        self.assertIn('simulation', self.window.badge.text())

    def test_unpair_cancel_and_save_failure_keep_connection(self):
        self.prepare_unpair()
        original = State.load(self.path)
        with patch.object(QMessageBox, 'exec', self.dialog_choice(QMessageBox.ButtonRole.RejectRole)):
            self.panel.disconnect_button.click()
        self.assertEqual(State.load(self.path), original)
        self.assertTrue(self.panel.timer.isActive())
        with patch.object(QMessageBox, 'exec', self.dialog_choice(QMessageBox.ButtonRole.DestructiveRole)), patch.object(State, 'save', side_effect=OSError('read only')):
            self.panel.disconnect_button.click()
        self.assertEqual(self.window.state, original)
        self.assertEqual(State.load(self.path), original)
        self.assertTrue(self.panel.timer.isActive())
        self.panel.timer.stop()

    def test_unpair_disabled_during_request(self):
        self.prepare_unpair()
        self.panel.busy = True
        self.panel.enable_controls()
        self.assertFalse(self.panel.disconnect_button.isEnabled())
        with patch.object(QMessageBox, 'exec') as dialog:
            self.panel.disconnect_bridge()
            dialog.assert_not_called()
        self.panel.timer.stop()
