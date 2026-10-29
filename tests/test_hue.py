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


    def test_partial_communication_error_is_actionable(self):
        conn = self.connection({'data': [], 'errors': [{'error_code': 'communication_error'}]}, 207)
        with patch('phihue.hue.http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(HueError, 'un foco no responde'):
                HueClient('192.168.1.20', 'key', PIN).request('PUT', '/clip/v2/resource/light/' + IDS[0], {'on': {'on': False}})


    def test_actual_reads_independent_color_brightness_and_power(self):
        client = HueClient('192.168.1.20', 'key', PIN)
        data = [{'id': IDS[0], 'on': {'on': True}, 'dimming': {'brightness': 21}, 'color': {'xy': {'x': .7, 'y': .299}}},
                {'id': IDS[1], 'on': {'on': False}, 'dimming': {'brightness': 88}, 'color': {'xy': {'x': .15, 'y': .06}}}]
        with patch.object(client, 'request', return_value=data) as request:
            snapshot = client.light_states(IDS)
            self.assertEqual([light['brightness'] for light in snapshot], [21, 88])
            self.assertEqual([light['on'] for light in snapshot], [True, False])
            self.assertNotEqual(snapshot[0]['color'], snapshot[1]['color'])
            request.assert_called_once_with('GET', '/clip/v2/resource/light')
        with patch.object(client, 'request') as request:
            client.set_power(IDS, False)
            self.assertTrue(all(call.args[2] == {'on': {'on': False}} for call in request.call_args_list))


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
        with patch.object(HueClient, 'pair', return_value=('key', PIN)), patch.object(HueClient, 'lights', return_value=LIGHTS), patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=[{'on': True, 'brightness': 70, 'color': '#ff0000'}] * 2):
            self.panel.address.setText('192.168.1.20')
            self.panel.pair_button.click()
            self.wait_idle()
            self.assertEqual(self.window.state.bridge.lights, LIGHTS)
            self.panel.selectors[0].setCurrentIndex(1)
            self.panel.selectors[1].setCurrentIndex(1)
            self.assertEqual(self.window.state.bridge.selected, [IDS[0], ''])
            self.panel.selectors[1].setCurrentIndex(2)
            self.assertTrue(self.window.state.bridge.ready)
            self.assertTrue(self.window.controls.isEnabled())
            self.assertTrue(self.window.settings_button.isEnabled())
            apply.assert_not_called()
            self.panel.schedule()
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[0], IDS)
            self.assertEqual(State.load(self.path).bridge.mode, 'real')
            self.assertTrue(self.window.badge.isHidden())
            self.window.adjust_brightness(10)
            self.window.adjust_brightness(30)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[2], 30)
            self.assertEqual(apply.call_count, 2)
            self.window.adjust_brightness(50)
            self.panel.connected = False
            self.panel.flush()
            self.assertEqual(apply.call_count, 2)

    def test_offline_error_and_no_real_mode_without_pairing(self):
        self.assertFalse(self.window.controls.isEnabled())
        self.assertEqual(self.window.state.bridge.mode, 'simulation')
        with patch('phihue.bridge_panel.discover', side_effect=HueError('No se pudo buscar el Bridge. Podés ingresar su IP manualmente.')):
            self.panel.search.click()
            self.wait_idle()
        self.assertIn('No se pudo buscar', self.panel.status.text())
        self.assertFalse(self.panel.pair_button.isEnabled())
        with patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=[{'on': True, 'brightness': 70, 'color': '#ff0000'}] * 2):
            self.window.adjust_brightness(40)
            self.panel.flush()
            apply.assert_not_called()

    def test_no_requests_on_reopen(self):
        state = State(bridge=BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real'))
        state.save(self.path)
        with patch.object(HueClient, 'request') as request:
            other = Window(self.path)
            QTest.qWait(20)
            self.assertTrue(all(call.args[0] == 'GET' for call in request.call_args_list))
            other.close()
            self.app.removeTranslator(other.qt_translator)

    def test_control_failure_keeps_configuration_and_can_retry(self):
        self.window.state.bridge = BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real')
        self.window.state.save(self.path)
        self.panel.connected = True
        self.panel.retranslate()
        with patch.object(HueClient, 'apply', side_effect=HueError('No se pudo contactar al Bridge. Revisá que estés en la misma red.')):
            self.panel.schedule()
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
        self.assertIn('No se pudo contactar', self.window.status.text())
        self.assertFalse(self.window.controls.isEnabled())
        self.assertTrue(self.window.settings_button.isEnabled())
        self.assertEqual(State.load(self.path).bridge.selected, IDS)
        with patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=[{'on': True, 'brightness': 70, 'color': '#ff0000'}] * 2):
            self.panel.connected = True
            self.panel.schedule()
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
        self.panel.connected = True
        self.window.refresh()
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
        self.assertIn('Not connected', self.window.badge.text())

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

    def test_accept_returns_after_save_and_light_error_keeps_controls(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        self.window.pages.setCurrentIndex(1)
        self.panel.retranslate()
        with patch.object(HueClient, 'light_states', return_value=[{'on': True, 'brightness': 70, 'color': '#ff0000'}] * 2):
            self.panel.accept_button.click()
            self.wait_idle()
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.assertEqual(State.load(self.path).bridge.selected, IDS)
        self.assertIn('Settings saved', self.window.status.text())
        message = 'El Bridge está conectado, pero un foco no responde. Revisá su alimentación y conexión en la app Hue; luego reintentá el cambio.'
        self.panel._controlling = True
        self.panel.finished(None, message)
        self.assertTrue(self.panel.connected)
        self.assertTrue(self.window.controls.isEnabled())

    def test_return_reads_power_without_writing_to_lights(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        for states in ([True, True], [False, False], [True, False]):
            self.window.pages.setCurrentIndex(1)
            self.window.state.powered = not any(states)
            with patch.object(HueClient, 'light_states', return_value=[{'on': on, 'brightness': 70, 'color': '#ff0000'} for on in states]), patch.object(HueClient, 'apply') as apply:
                self.window.back_button.click()
                self.wait_idle()
                apply.assert_not_called()
            self.assertEqual(self.window.pages.currentIndex(), 0)
            self.assertEqual(self.window.power.isChecked(), any(states))
            self.assertEqual(self.window.observed_power, states)

    def test_return_failure_stays_in_settings(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        self.window.pages.setCurrentIndex(1)
        with patch.object(HueClient, 'light_states', side_effect=HueError('No se pudo contactar al Bridge. Revisá que estés en la misma red.')):
            self.window.back_button.click()
            self.wait_idle()
        self.assertEqual(self.window.pages.currentIndex(), 1)
        self.assertFalse(self.window.controls.isEnabled())

    def test_startup_reads_actual_power_before_enabling_controls(self):
        for states in ([True, True], [False, False], [True, False]):
            state = State(bridge=BridgeSettings('192.168.1.20', 'key', PIN, LIGHTS, IDS, 'real'))
            state.powered = not any(states)
            state.save(self.path)
            with patch.object(HueClient, 'lights', return_value=LIGHTS), patch.object(HueClient, 'light_states', return_value=[{'on': on, 'brightness': 70, 'color': '#ff0000'} for on in states]) as read, patch.object(HueClient, 'apply') as apply:
                other = Window(self.path)
                self.assertFalse(other.controls.isEnabled())
                until = time.monotonic() + 3
                while not other.controls.isEnabled() and time.monotonic() < until:
                    QTest.qWait(10)
                self.assertTrue(other.controls.isEnabled())
                self.assertEqual(other.power.isChecked(), any(states))
                self.assertEqual(other.observed_power, states)
                read.assert_called_once_with(IDS)
                apply.assert_not_called()
                other.close()
                self.app.removeTranslator(other.qt_translator)

    def test_actual_keeps_scenes_and_displays_individual_values(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        scenes = deepcopy(self.window.state.schemes)
        snapshot = [{'on': True, 'brightness': 23, 'color': '#ff0000'},
                    {'on': False, 'brightness': 87, 'color': '#0011ff'}]
        with patch.object(HueClient, 'light_states', return_value=snapshot), patch.object(HueClient, 'apply') as apply:
            self.window.actual_button.click()
            self.wait_idle()
            apply.assert_not_called()
        self.assertTrue(self.window.actual_view)
        self.assertEqual(self.window.state.schemes, scenes)
        self.assertIn('23%', self.window.actual_labels[0].text())
        self.assertIn('87%', self.window.actual_labels[1].text())
        self.assertIn('Off', self.window.actual_labels[1].text())
        with patch.object(self.panel, 'schedule') as schedule:
            self.window.select(2)
            self.assertFalse(self.window.actual_view)
            schedule.assert_called_once()
        self.assertEqual(self.window.state.schemes, scenes)

    def test_actual_power_does_not_apply_scene_colors_or_brightness(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        snapshot = [{'on': True, 'brightness': 23, 'color': '#ff0000'},
                    {'on': False, 'brightness': 87, 'color': '#0011ff'}]
        scenes = deepcopy(self.window.state.schemes)
        self.window.receive_actual(snapshot)
        off = [dict(light, on=False) for light in snapshot]
        with patch.object(HueClient, 'set_power') as power, patch.object(HueClient, 'light_states', return_value=off), patch.object(HueClient, 'apply') as apply:
            self.window.toggle_power()
            self.wait_idle()
            power.assert_called_once_with(IDS, False)
            apply.assert_not_called()
        self.assertEqual(self.window.state.schemes, scenes)
        self.assertEqual(self.window.actual, off)

    def test_actual_edits_only_changed_fields_and_preserves_scenes(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        self.panel.pending = None
        snapshot = [{'on': True, 'brightness': 23, 'color': '#ff0000'},
                    {'on': True, 'brightness': 87, 'color': '#0011ff'}]
        self.window.receive_actual(snapshot)
        scenes = deepcopy(self.window.state.schemes)
        with patch.object(HueClient, 'request', return_value=[]) as request:
            self.window.edit_actual(0, color='#00ff00')
            self.window.actual_sliders[1].setValue(40)
            self.window.actual_sliders[1].setValue(65)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
        self.assertEqual(request.call_count, 2)
        first, second = request.call_args_list
        self.assertEqual(set(first.args[2]), {'color'})
        self.assertTrue(first.args[1].endswith(IDS[0]))
        self.assertEqual(second.args[2], {'dimming': {'brightness': 65.0}})
        self.assertTrue(second.args[1].endswith(IDS[1]))
        self.assertEqual(self.window.state.schemes, scenes)
        self.assertEqual(State.load(self.path).schemes, scenes)
        self.assertEqual(self.window.actual[0]['brightness'], 23)
        self.assertEqual(self.window.actual[1]['color'], '#0011ff')

    def test_scene_refreshes_actual_without_changing_selected_scene(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        snapshot = [{'on': True, 'brightness': 74.9, 'color': '#ffc18a'},
                    {'on': True, 'brightness': 75, 'color': '#8abaff'}]
        scenes = deepcopy(self.window.state.schemes)
        with patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=snapshot) as read:
            self.window.select(3)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            apply.assert_called_once()
            read.assert_called_once_with(IDS)
        self.assertEqual(self.window.actual, snapshot)
        self.assertFalse(self.window.actual_view)
        self.assertEqual(self.window.state.selected, 3)
        self.assertTrue(self.window.buttons[3].isChecked())
        self.assertEqual(self.window.actual_button.scheme.colors, [light['color'] for light in snapshot])
        self.assertEqual(self.window.state.schemes, scenes)

    def test_save_actual_to_named_slot_roundtrips_and_does_not_touch_lights(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        self.panel.pending = None
        snapshot = [{'on': True, 'brightness': 24.5, 'color': '#ff0000'},
                    {'on': False, 'brightness': 87, 'color': '#0011ff'}]
        self.window.receive_actual(snapshot)
        before = deepcopy(self.window.state.schemes)
        with patch.object(HueClient, 'request') as request:
            self.assertTrue(self.window.store_actual(2, 'Mi escena'))
            request.assert_not_called()
        saved = State.load(self.path)
        self.assertEqual(saved.schemes[2].name, 'Mi escena')
        self.assertEqual(saved.schemes[2].brightnesses, [24.5, 87])
        self.assertEqual(saved.schemes[2].powers, [True, False])
        self.assertEqual(saved.schemes[2].colors, ['#ff0000', '#0011ff'])
        self.assertTrue(self.window.actual_view)
        for i in (0, 1, 3, 4):
            self.assertEqual(saved.schemes[i], before[i])
        with patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=snapshot):
            self.window.select(2)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[2:], ([24.5, 87], [True, False]))

    def test_save_actual_failure_keeps_original_slot(self):
        self.window.receive_actual([{'on': True, 'brightness': 50, 'color': '#ffffff'}] * 2)
        before = deepcopy(self.window.state.schemes)
        with patch.object(State, 'save', side_effect=OSError('disk error')), patch.object(QMessageBox, 'warning'):
            self.assertFalse(self.window.store_actual(0, 'New'))
        self.assertEqual(self.window.state.schemes, before)

    def test_scene_edits_are_live_but_only_saved_explicitly(self):
        self.prepare_unpair()
        self.panel.timer.stop()
        self.panel.pending = None
        baseline = deepcopy(State.load(self.path).schemes)
        self.window.actual_view = False
        self.window.name.setText('Nueva escena')
        self.window.rename()
        self.window.draft_scene().set_color(0, '#123456')
        with patch.object(HueClient, 'apply') as apply, patch.object(HueClient, 'light_states', return_value=[{'on': True, 'brightness': 44, 'color': '#123456'}] * 2):
            self.window.adjust_brightness(44)
            self.panel.timer.stop()
            self.panel.flush()
            self.wait_idle()
            self.assertEqual(apply.call_args.args[1][0], '#123456')
            self.assertEqual(apply.call_args.args[2], 44)
        self.assertEqual(State.load(self.path).schemes, baseline)
        self.window.language_selector.setCurrentIndex(0)
        self.assertEqual(State.load(self.path).schemes, baseline)
        self.assertTrue(self.window.save_scene())
        saved = State.load(self.path).current
        self.assertEqual(saved.name, 'Nueva escena')
        self.assertEqual(saved.colors[0], '#123456')
        self.assertEqual(saved.brightness, 44)
        self.assertNotIn(self.window.state.selected, self.window.scene_drafts)

    def test_scene_save_failure_retains_draft_and_original(self):
        baseline = deepcopy(self.window.state.current)
        self.window.name.setText('Draft')
        self.window.rename()
        with patch.object(State, 'save', side_effect=OSError('disk error')), patch.object(QMessageBox, 'warning'):
            self.assertFalse(self.window.save_scene())
        self.assertEqual(self.window.state.current, baseline)
        self.assertEqual(self.window.editing_scene.name, 'Draft')
        self.assertEqual(State.load(self.path).current, baseline)
