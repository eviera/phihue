import tempfile
import json
import unittest
from pathlib import Path
from phihue.model import State

class StateTests(unittest.TestCase):
    def test_link_and_unlink(self):
        s = State().current
        s.set_color(1, '#112233')
        self.assertEqual(s.colors, ['#112233', '#112233'])
        s.set_linked(False)
        s.set_color(1, '#abcdef')
        self.assertEqual(s.colors, ['#112233', '#abcdef'])
        s.set_linked(True)
        self.assertEqual(s.colors, ['#112233', '#112233'])

    def test_schemes_are_independent(self):
        state = State()
        state.current.set_color(0, '#123456')
        state.current.brightness = 0
        state.selected = 1
        self.assertNotEqual(state.current.colors[0], '#123456')
        self.assertEqual(state.current.brightness, 75)
        self.assertEqual(len(state.schemes), 5)

    def test_roundtrip_including_power(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data' / 'state.json'
            state = State()
            state.selected = 3
            state.powered = False
            state.language = 'en'
            state.current.name = 'Personalizado'
            state.current.brightness = 42
            state.current.set_linked(False)
            state.current.set_color(1, '#123abc')
            state.save(path)
            self.assertEqual(State.load(path), state)

    def test_legacy_and_unknown_language_preserve_scenes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            state = State()
            state.current.name = 'Mi ambiente'
            state.save(path)
            data = json.loads(path.read_text())
            del data['language']
            for language in (None, 'unknown'):
                if language is not None:
                    data['language'] = language
                path.write_text(json.dumps(data))
                loaded = State.load(path)
                self.assertEqual(loaded.language, 'es')
                self.assertEqual(loaded.current.name, 'Mi ambiente')

    def test_invalid_saved_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            state = State()
            state.selected = -1
            state.save(path)
            with self.assertRaises(AssertionError):
                State.load(path)

if __name__ == '__main__':
    unittest.main()
