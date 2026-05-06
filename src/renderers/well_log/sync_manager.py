from PySide6.QtCore import QObject, Slot

class SyncManager(QObject):
    def __init__(self):
        super().__init__()
        self._engines = []
        self._is_syncing = False

    def register_engine(self, engine):
        if engine not in self._engines:
            self._engines.append(engine)
            engine.bridge.zoom_changed.connect(lambda s, e: self.sync_range(engine, s, e))

    def unregister_engine(self, engine):
        if engine in self._engines:
            self._engines.remove(engine)

    def sync_range(self, source_engine, start, end):
        if self._is_syncing:
            return
        self._is_syncing = True
        try:
            for engine in self._engines:
                if engine != source_engine:
                    engine.view.page().runJavaScript(f"window.geoviz.setRange({start}, {end});")
        finally:
            self._is_syncing = False
