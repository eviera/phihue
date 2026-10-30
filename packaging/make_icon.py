"""Convert the approved PNG artwork into the macOS ICNS container."""
import struct
from pathlib import Path
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

source = Path(__file__).resolve().parent.parent / 'phihue' / 'assets' / 'icon.png'
image = QImage(str(source))
if image.isNull():
    raise RuntimeError(f'Cannot load icon: {source}')
chunks = []
for kind, size in [('icp4', 16), ('icp5', 32), ('icp6', 64), ('ic07', 128),
                   ('ic08', 256), ('ic09', 512), ('ic10', 1024)]:
    resized = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not resized.save(buffer, 'PNG'):
        raise RuntimeError('Cannot encode icon')
    data = bytes(buffer.data())
    chunks.append(kind.encode() + struct.pack('>I', len(data) + 8) + data)
payload = b''.join(chunks)
(Path(__file__).parent / 'PhiHue.icns').write_bytes(b'icns' + struct.pack('>I', len(payload) + 8) + payload)
