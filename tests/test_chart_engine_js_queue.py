"""#715: ChartEngine JS queue/flush without constructing QWebEngineView."""

from geoviz_well_log.chart_engine import ChartEngine


class _FakePage:
    def __init__(self):
        self.scripts = []

    def runJavaScript(self, js):
        self.scripts.append(js)


class _FakeView:
    def __init__(self):
        self._page = _FakePage()

    def page(self):
        return self._page


def _engine_with_spy(qtbot):
    view = _FakeView()
    engine = ChartEngine(view=view)
    qtbot.addWidget(engine)
    return engine, view


def test_render_data_queues_js_until_web_ready(qtbot):
    engine, view = _engine_with_spy(qtbot)
    spy = view.page().scripts

    engine.render_data("{}")

    assert spy == []
    assert engine._js_queue == ["window.geoviz.render({});"]

    engine._on_web_ready()

    assert "window.geoviz.render({});" in spy
    assert engine._js_queue == []


def test_export_svg_queues_until_web_ready(qtbot):
    engine, view = _engine_with_spy(qtbot)
    spy = view.page().scripts

    engine.export_svg()

    assert spy == []
    queued = "\n".join(engine._js_queue)
    assert "exportChartToSvg" in queued
    assert "receive_svg" in queued

    engine._on_web_ready()

    flushed = "\n".join(spy)
    assert "exportChartToSvg" in flushed
    assert "receive_svg" in flushed
    assert engine._js_queue == []


def test_render_data_after_ready_runs_js_immediately(qtbot):
    engine, view = _engine_with_spy(qtbot)
    spy = view.page().scripts

    engine._on_web_ready()
    n_after_ready = len(spy)

    engine.render_data('{"well":"A1"}')

    assert "window.geoviz.render({\"well\":\"A1\"});" in spy[n_after_ready:]
    assert engine._js_queue == []
