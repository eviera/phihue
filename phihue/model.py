"""Shared scene, language and Bridge settings. No network access here."""
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
import re
import os
from uuid import UUID


@dataclass
class BridgeSettings:
    address: str = ''
    key: str = field(default='', repr=False)
    fingerprint: str = ''
    lights: list[dict] = field(default_factory=list)
    selected: list[str] = field(default_factory=lambda: ['', ''])
    mode: str = 'simulation'

    @property
    def ready(self):
        available = {light['id'] for light in self.lights}
        return bool(self.address and self.key and self.fingerprint
                    and len(self.selected) == 2 and len(set(self.selected)) == 2
                    and all(item in available for item in self.selected))

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return cls()
        try:
            result = cls(**data)
            if not all(isinstance(value, str) for value in (result.address, result.key, result.fingerprint)):
                return cls()
            if result.fingerprint and not re.fullmatch(r'[0-9a-f]{64}', result.fingerprint):
                return cls()
            if not isinstance(result.lights, list) or not isinstance(result.selected, list) or len(result.selected) != 2:
                return cls()
            for light in result.lights:
                UUID(light['id'])
                if not isinstance(light['name'], str):
                    return cls()
            for item in result.selected:
                if item:
                    UUID(item)
            if result.mode != 'real' or not result.ready:
                result.mode = 'simulation'
            return result
        except (TypeError, ValueError, KeyError, AttributeError):
            return cls()

@dataclass
class Scheme:
    name: str
    colors: list[str]
    linked: bool = True
    brightness: int = 75
    brightnesses: list[float] | None = None
    powers: list[bool] | None = None

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
    bridge: BridgeSettings = field(default_factory=BridgeSettings)

    @property
    def current(self):
        return self.schemes[self.selected]

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(asdict(self), ensure_ascii=False, indent=2))
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
            if scheme.brightnesses is not None:
                assert len(scheme.brightnesses) == 2 and all(type(v) in (int, float) and 0 <= v <= 100 for v in scheme.brightnesses)
            if scheme.powers is not None:
                assert len(scheme.powers) == 2 and all(type(v) is bool for v in scheme.powers)
            schemes.append(scheme)
        language = data.get('language', 'es')
        if language not in ('es', 'en'):
            language = 'es'
        return cls(schemes, data['selected'], data['powered'], language,
                   BridgeSettings.from_dict(data.get('bridge', {})))
