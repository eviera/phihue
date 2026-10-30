"""PyInstaller entry point; private smoke mode never reads the user's Bridge."""
import sys

from phihue.__main__ import main

if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        import tempfile
        from pathlib import Path
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from phihue.__main__ import Window, default_state_path
        app = QApplication([])
        app.setStyle('Fusion')
        with tempfile.TemporaryDirectory() as directory:
            window = Window(Path(directory) / 'state.json')
            window.show()
            def finish():
                assert window.isVisible()
                assert not window.controls.isEnabled()
                window.language_selector.setCurrentIndex(1)
                assert window.back_button.text() == '← Back'
                window.grab().save('/tmp/phihue-packaged.png')
                print('SMOKE OK; state path:', default_state_path(), flush=True)
                app.quit()
            QTimer.singleShot(500, finish)
            sys.exit(app.exec())
    else:
        main()
