"""
Browser-Tests (Playwright/WebKit = Safari-Engine) gegen einen echten, frisch gestarteten Server.

Der Server läuft als eigener Prozess mit leerem Datenverzeichnis, ohne API-Key und ohne
Hintergrund-Worker. Ohne installiertes Playwright werden die Tests übersprungen
(Einrichtung: .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m playwright install webkit).
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARENT_PIN = "1234"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def parent_pin():
    return PARENT_PIN


@pytest.fixture(scope="session")
def server_data_dir():
    """Datenverzeichnis des Testservers (z. B. um erschlossene Seiten direkt anzulegen)."""
    return tempfile.mkdtemp(prefix="gothea_e2e_")


@pytest.fixture(scope="session")
def server_url(server_data_dir):
    data_dir = server_data_dir
    port = _free_port()
    env = {
        **os.environ,
        "APP_ENV": "staging",
        "DATA_DIR": data_dir,
        "INBOX_DIR": os.path.join(data_dir, "inbox"),
        "SHARED_DATA_DIR": os.path.join(data_dir, "shared"),
        "DATABASE_URL": f"sqlite:///{data_dir}/app_data.db",
        "OPENAI_API_KEY": "",
        "GOTHEA_BACKGROUND_WORKERS": "0",
        "GOTHEA_EXERCISE_POOL": "0",
        "GOTHEA_PARENT_PIN": PARENT_PIN,
    }
    log = open(os.path.join(data_dir, "server.log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while True:
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=1)
            break
        except Exception:
            if proc.poll() is not None or time.time() > deadline:
                proc.kill()
                pytest.fail(f"Testserver startet nicht, siehe {log.name}")
            time.sleep(0.2)
    yield url
    proc.terminate()
    proc.wait(timeout=10)
    log.close()


@pytest.fixture(scope="session")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"WebKit nicht installiert ({e.__class__.__name__}): python -m playwright install webkit")
        # Theas Gerät: iPad im Querformat
        device = p.devices["iPad Pro 11 landscape"]
        yield b, device
        b.close()


class PageProblems:
    """Sammelt JS-Fehler, Konsolen-Fehler und fehlgeschlagene API-Antworten einer Seite."""

    def __init__(self, page):
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(f"JS-Fehler: {e}"))
        page.on("console", lambda m: m.type == "error" and self.errors.append(f"Konsole: {m.text}"))
        page.on("response", self._on_response)

    def _on_response(self, response):
        if "/api/" in response.url and response.status >= 400:
            self.errors.append(f"HTTP {response.status}: {response.request.method} {response.url}")


@pytest.fixture
def app_page(browser, server_url):
    """Frisch geladene Startseite; der Test schlägt fehl, wenn dabei Fehler auftreten."""
    b, device = browser
    context = b.new_context(**device)
    page = context.new_page()
    problems = PageProblems(page)
    page.goto(server_url)
    page.wait_for_load_state("networkidle")
    page.problems = problems
    yield page
    context.close()
