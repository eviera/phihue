"""Estado local del simulador. No contiene acceso a red."""
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
import re

@dataclass
class Scheme:
    name: str
    colors: list[str]
    linked: bool = True
    brightness: int = 75

    def set_color(self, index, color):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Color inválido')
        self.colors[index] = color
        if self.linked:
            self.colors = [color, color]

    def set_linked(self, linked):
        self.linked = linked
        if linked:
            self.colors[1] = self.colors[0]


def defaults():
    return [Scheme(name, [color, color]) for name, color in [
        ('Lectura', '#ffd39a'), ('Concentración', '#dbeaff'),
        ('Relax', '#ffab70'), ('Atardecer', '#ff718e'), ('Noche', '#9c8cff')]]

@dataclass
class State:
    schemes: list[Scheme] = field(default_factory=defaults)
    selected: int = 0
    powered: bool = True
    language: str = 'es'

    @property
    def current(self):
        return self.schemes[self.selected]

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        assert type(data['selected']) is int and 0 <= data['selected'] < 5
        assert type(data['powered']) is bool and len(data['schemes']) == 5
        schemes = []
        for item in data['schemes']:
            scheme = Scheme(**item)
            assert isinstance(scheme.name, str) and 0 < len(scheme.name.strip()) <= 32
            assert type(scheme.linked) is bool
            assert type(scheme.brightness) is int and 0 <= scheme.brightness <= 100
            assert isinstance(scheme.colors, list) and len(scheme.colors) == 2
            assert all(isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in scheme.colors)
            assert not scheme.linked or scheme.colors[0] == scheme.colors[1]
            schemes.append(scheme)
        language = data.get('language', 'es')
        if language not in ('es', 'en'):
            language = 'es'
        return cls(schemes, data['selected'], data['powered'], language)
