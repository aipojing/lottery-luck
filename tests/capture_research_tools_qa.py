"""Capture real-browser acceptance screenshots for the research center and number tools.

Serves the real FastAPI app (local runtime database) and drives a real Chromium:
- artifacts/research-center-data-desktop.png      1440x1000 /analysis.html?game=ssq&view=data
- artifacts/research-center-strategy-mobile.png   390x844   /analysis.html?game=3d&view=strategy
- artifacts/number-tools-conditional-desktop.png  1440x1000 /tools.html?game=3d&tool=conditional
                                                  with generated results and a visible basket
"""

import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from lottery_luck.api import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT_ROOT / "artifacts"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(base):
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise SystemExit("live server did not become ready")


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    _wait_ready(base)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{base}/analysis.html?game=ssq&view=data", wait_until="networkidle")
        page.wait_for_selector("#researchDataView:not([hidden])")
        page.wait_for_selector("#commonViewPanel")
        page.wait_for_timeout(600)
        page.screenshot(path=str(ARTIFACTS / "research-center-data-desktop.png"))
        page.close()

        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{base}/analysis.html?game=3d&view=strategy", wait_until="networkidle")
        page.wait_for_selector("#researchStrategyView:not([hidden])")
        page.wait_for_selector("#strategyForm")
        page.wait_for_timeout(600)
        page.screenshot(path=str(ARTIFACTS / "research-center-strategy-mobile.png"))
        page.close()

        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{base}/tools.html?game=3d&tool=conditional", wait_until="networkidle")
        page.wait_for_selector("#conditionalDigitFields")
        page.click('#toolWorkbench button[type="submit"]')
        page.wait_for_selector("[data-result-entry]", timeout=15000)
        page.click("#addAllResults")
        page.wait_for_function(
            "() => document.querySelectorAll('#basketEntries li').length > 0"
        )
        page.wait_for_timeout(600)
        page.evaluate(
            """() => {
              const result = document.querySelector("#toolResult");
              window.scrollTo(0, result.getBoundingClientRect().top + window.scrollY - 20);
            }"""
        )
        page.wait_for_timeout(300)
        if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
            raise RuntimeError("number tools conditional view has horizontal overflow at 1440px")
        if not page.evaluate(
            """() => ["#toolResult", "#toolBasket"].every((selector) => {
              const rect = document.querySelector(selector).getBoundingClientRect();
              return rect.bottom > 0 && rect.top < window.innerHeight;
            })"""
        ):
            raise RuntimeError("number tools capture must show generated results and the number basket together")
        page.screenshot(path=str(ARTIFACTS / "number-tools-conditional-desktop.png"))
        page.close()

        browser.close()

    server.should_exit = True
    thread.join(timeout=5)
    print("Screenshots written to artifacts/")


if __name__ == "__main__":
    sys.exit(main())
