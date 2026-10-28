import tempfile
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
            state.current.name = 'Personalizado'
            state.current.brightness = 42
            state.current.set_linked(False)
            state.current.set_color(1, '#123abc')
            state.save(path)
            self.assertEqual(State.load(path), state)

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
