# Build with: .venv/bin/python -m PyInstaller --noconfirm PhiHue.spec
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'packaging' / 'app_entry.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root / 'phihue' / 'assets' / 'icon.png'), 'phihue/assets')], hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PhiHue',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PhiHue')
app = BUNDLE(coll, name='PhiHue.app', icon=str(root / 'packaging' / 'PhiHue.icns'),
             bundle_identifier='com.eviera.phihue', version='0.1.0',
             info_plist={'CFBundleDisplayName': 'PhiHue',
                         'NSHighResolutionCapable': True,
                         'NSLocalNetworkUsageDescription': 'PhiHue se conecta a tu Hue Bridge para controlar las luces de tu red local.'})
