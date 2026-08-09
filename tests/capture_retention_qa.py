"""Deterministic visual capture for the 福彩3D toolbox release QA.

Run from the worktree root:

    PYTHONPATH=. ../../.venv/bin/python tests/capture_retention_qa.py

The harness never touches `cwl_history/cwl_history.sqlite`: every capture serves a fresh
temporary SQLite fixture, a fixed `today`, disabled auto-update and a browser context that
aborts any request leaving the local server. The journey is captured twice against
independent databases and browsers, and the two passes must produce byte-identical PNGs.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import uvicorn
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from lottery_luck.api import app, get_repository
from lottery_luck.repository import LotteryRepository
from tests.test_retention_flow import (
    CLIENT_ID,
    TODAY,
    _build_isolated_repo,
    _free_port,
    _install_client_id,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

DESKTOP = {"width": 1440, "height": 1000}
MOBILE = {"width": 390, "height": 844}

STALE_LATEST_DATE = date(2026, 7, 5)

SCREENSHOTS = {
    "toolbox_home_desktop": ARTIFACTS / "fc3d-toolbox-home-desktop.png",
    # The first screen of a 390px phone, captured at exactly the fold (not full page), so the
    # release bar below can be read straight off the image.
    "toolbox_home_mobile": ARTIFACTS / "fc3d-toolbox-home-mobile.png",
    "toolbox_trend_desktop": ARTIFACTS / "fc3d-toolbox-trend-desktop.png",
    "toolbox_stale_mobile": ARTIFACTS / "fc3d-toolbox-stale-mobile.png",
}

# The toolbox home must lead with the data status and enough tools to choose from, on the
# first screen of a 390px phone. Both numbers are asserted, not eyeballed.
MOBILE_FIRST_SCREEN_MIN_TOOLS = 6

TOOL_KEYS = (
    "trend",
    "omission",
    "frequency",
    "heat",
    "number",
    "attributes",
    "recent",
)

DETERMINISTIC_PAGE_SCRIPT = """
(() => {
  const NativeDate = Date;
  const fixedNow = NativeDate.parse("2026-07-13T04:00:00.000Z");
  class FixedBrowserDate extends NativeDate {
    constructor(...args) {
      super(...(args.length ? args : [fixedNow]));
    }
    static now() {
      return fixedNow;
    }
  }
  window.Date = FixedBrowserDate;
  Math.random = () => 0.125;

  const installCaptureStyle = () => {
    if (!document.head || document.querySelector("#retention-capture-stability")) return false;
    const style = document.createElement("style");
    style.id = "retention-capture-stability";
    style.textContent = `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
        scroll-behavior: auto !important;
      }
    `;
    document.head.append(style);
    return true;
  };
  if (!installCaptureStyle()) {
    const observer = new MutationObserver(() => {
      if (installCaptureStyle()) observer.disconnect();
    });
    observer.observe(document, {childList: true, subtree: true});
  }
})();
"""


class FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return TODAY


def fixed_current_day(value: date | str | None = None) -> date:
    if value is None:
        return TODAY
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


@contextmanager
def served_repo(repo: LotteryRepository):
    """Serve one temporary repository with AI and auto-update off and time frozen."""
    previous_env = {
        key: os.environ.get(key)
        for key in ("LOTTERY_LUCK_AI_ENABLED", "LOTTERY_LUCK_AUTO_UPDATE_ENABLED")
    }
    os.environ["LOTTERY_LUCK_AI_ENABLED"] = "0"
    os.environ["LOTTERY_LUCK_AUTO_UPDATE_ENABLED"] = "false"
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            # lifespan off keeps the auto-update scheduler from ever starting.
            lifespan="off",
            log_level="warning",
        )
    )
    app.dependency_overrides[get_repository] = lambda: repo

    with (
        patch("lottery_luck.data_health._current_day", fixed_current_day),
        patch("lottery_luck.workbench_routes.date", FixedDate),
    ):
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.time() + 10
        while not server.started:
            if time.time() > deadline:
                server.should_exit = True
                raise RuntimeError("uvicorn capture server did not start")
            time.sleep(0.02)
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            app.dependency_overrides.clear()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fc3d-toolbox-qa-") as temp_root:
        temp_path = Path(temp_root)
        with sync_playwright() as playwright:
            first = capture_once(playwright, temp_path / "first", SCREENSHOTS)
            repeat_dir = temp_path / "repeat-artifacts"
            repeat_dir.mkdir()
            repeat_outputs = {
                key: repeat_dir / output.name for key, output in SCREENSHOTS.items()
            }
            repeat = capture_once(playwright, temp_path / "repeat", repeat_outputs)

    first_results = first["artifacts"]
    repeat_results = repeat["artifacts"]
    mismatches = {
        key: {
            "first": first_results[key]["sha256"],
            "repeat": repeat_results[key]["sha256"],
        }
        for key in SCREENSHOTS
        if first_results[key]["sha256"] != repeat_results[key]["sha256"]
    }
    assert not mismatches, f"capture SHA-256 mismatch: {json.dumps(mismatches, indent=2)}"
    print(
        json.dumps(
            {
                "artifacts": first_results,
                "mobile_first_screen": first["mobile_first_screen"],
                "repeat_sha256_verified": {
                    key: first_results[key]["sha256"] for key in SCREENSHOTS
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def capture_once(
    playwright: Playwright,
    temp_path: Path,
    outputs: dict[str, Path],
) -> dict[str, Any]:
    temp_path.mkdir()
    fresh_repo = _build_isolated_repo(temp_path / "fresh.sqlite")
    stale_repo = _build_isolated_repo(
        temp_path / "stale.sqlite",
        latest_date=STALE_LATEST_DATE,
    )
    results: dict[str, dict[str, Any]] = {}
    browser = playwright.chromium.launch(headless=True)
    try:
        with served_repo(fresh_repo) as fresh_url:
            fresh = capture_fresh_toolbox(browser, fresh_url, outputs)
            results.update(fresh["artifacts"])
        with served_repo(stale_repo) as stale_url:
            results["toolbox_stale_mobile"] = capture_stale_mobile(
                browser,
                stale_url,
                outputs["toolbox_stale_mobile"],
            )
    finally:
        browser.close()
    return {"artifacts": results, "mobile_first_screen": fresh["mobile_first_screen"]}


def new_capture_page(browser: Browser, viewport: dict[str, int], base_url: str) -> Page:
    page = browser.new_page(
        viewport=viewport,
        reduced_motion="reduce",
        color_scheme="light",
        forced_colors="none",
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        device_scale_factor=1,
        service_workers="block",
    )
    page.add_init_script(DETERMINISTIC_PAGE_SCRIPT)
    block_external_network(page, base_url)
    return page


def block_external_network(page: Page, base_url: str) -> None:
    """No capture may depend on anything outside the local fixture server."""

    def route(handler_route) -> None:
        if handler_route.request.url.startswith(base_url):
            handler_route.continue_()
            return
        handler_route.abort()

    page.route("**/*", route)


def capture_fresh_toolbox(
    browser: Browser,
    base_url: str,
    outputs: dict[str, Path],
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}

    page = new_capture_page(browser, DESKTOP, base_url)
    try:
        _install_client_id(page, base_url, CLIENT_ID)
        page.goto(f"{base_url}/analysis.html?game=3d")
        wait_for_toolbox_home(page)
        assert_toolbox_home(page)
        results["toolbox_home_desktop"] = screenshot_and_assert(
            page,
            outputs["toolbox_home_desktop"],
            DESKTOP,
        )

        page.get_by_role("button", name="走势图").click()
        page.wait_for_url("**tool=trend&window=30")
        wait_for_trend_tool(page)
        assert_trend_tool(page)
        results["toolbox_trend_desktop"] = screenshot_and_assert(
            page,
            outputs["toolbox_trend_desktop"],
            DESKTOP,
        )
    finally:
        page.close()

    mobile = new_capture_page(browser, MOBILE, base_url)
    try:
        _install_client_id(mobile, base_url, CLIENT_ID)
        mobile.goto(f"{base_url}/analysis.html?game=3d")
        wait_for_toolbox_home(mobile)
        first_screen = measure_mobile_first_screen(mobile)
        results["toolbox_home_mobile"] = screenshot_and_assert(
            mobile,
            outputs["toolbox_home_mobile"],
            MOBILE,
            full_page=False,
        )
    finally:
        mobile.close()

    return {"artifacts": results, "mobile_first_screen": first_screen}


def capture_stale_mobile(browser: Browser, base_url: str, output: Path) -> dict[str, Any]:
    page = new_capture_page(browser, MOBILE, base_url)
    try:
        _install_client_id(page, base_url, CLIENT_ID)

        # Stale data must not take the history tools away: every one of them still renders
        # a real result before the disabled current-issue state is captured.
        assert_history_tools_readable_when_stale(page, base_url)

        page.goto(f"{base_url}/analysis.html?game=3d")
        wait_for_toolbox_home(page)
        assert_text_visible(page, "#threeDFreshness", "数据待更新")
        assert_text_visible(page, "#threeDFreshness", STALE_LATEST_DATE.isoformat())
        assert_no_page_horizontal_overflow(page)
        assert_not_loading_or_error(page)
        return screenshot_and_assert(page, output, MOBILE)
    finally:
        page.close()


def assert_history_tools_readable_when_stale(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/analysis.html?game=3d&tool=trend&window=30")
    wait_for_trend_tool(page)
    rows = page.locator("#threeDTrendPanel table tbody tr").count()
    assert rows >= 10, rows

    page.goto(f"{base_url}/analysis.html?game=3d&tool=recent")
    page.wait_for_selector('[data-three-d-tool-panel="recent"]:not([hidden])')
    page.wait_for_function(
        "() => document.querySelectorAll('#threeDRecentDraws li').length >= 10",
        timeout=8000,
    )

    page.goto(f"{base_url}/analysis.html?game=3d&tool=omission&window=30")
    page.wait_for_selector('[data-three-d-tool-panel="omission"]:not([hidden])')
    page.wait_for_function(
        "() => document.querySelector('#threeDOmissionMatrix table') !== null",
        timeout=8000,
    )

    page.goto(f"{base_url}/analysis.html?game=3d&tool=number")
    page.wait_for_selector('[data-three-d-tool-panel="number"]:not([hidden])')
    page.locator("#threeDNumberQueryInput").fill("006")
    with page.expect_response("**/api/3d/number**"):
        page.locator("#threeDNumberQueryForm button[type='submit']").click()
    page.wait_for_function(
        "() => !/等待查询/.test(document.querySelector('#threeDNumberQueryResult')?.textContent || '等待查询')",
        timeout=8000,
    )
    assert page.locator("#threeDNumberQueryResult").inner_text().strip()


def wait_for_toolbox_home(page: Page) -> None:
    page.wait_for_function(
        """
        (expectedTools) => {
          const home = document.querySelector("#threeDToolHome");
          const tiles = document.querySelectorAll("[data-three-d-tool-key]");
          return Boolean(
            home
              && !home.hidden
              && tiles.length === expectedTools
              && document.querySelector("#threeDFreshness")?.textContent.includes("2026"),
          );
        }
        """,
        arg=len(TOOL_KEYS),
        timeout=8000,
    )


def wait_for_trend_tool(page: Page) -> None:
    page.wait_for_selector('[data-three-d-tool-panel="trend"]:not([hidden])')
    page.wait_for_function(
        "() => document.querySelector('#threeDTrendPanel table tbody tr') !== null",
        timeout=8000,
    )


def assert_toolbox_home(page: Page) -> None:
    assert_text_visible(page, "#threeDToolboxTitle", "福彩3D工具箱")
    assert_text_visible(page, "#threeDFreshness", "最新")
    assert_text_visible(page, "#threeDFreshness", "本期")
    for key in TOOL_KEYS:
        tile = page.locator(f'[data-three-d-tool-key="{key}"]')
        assert tile.is_visible(), key
    assert page.locator("#threeDToolWorkspace").is_hidden()
    assert_no_page_horizontal_overflow(page)
    assert_not_loading_or_error(page)
    assert_text_not_clipped(page, ["[data-three-d-tool-key]", ".three-d-history-link"])
    assert_no_key_overlap(page, ["[data-three-d-tool-key]"])
    assert_tap_targets(page)


def assert_trend_tool(page: Page) -> None:
    assert_text_visible(page, "#threeDToolTitle", "走势图")
    # The window, the real sample, the latest data date and the disclaimer are visible with no
    # click; only the mechanics of the statistic sit behind the 说明 disclosure.
    assert_text_visible(page, "#threeDToolDefinition", "近30期")
    assert_text_visible(page, "#threeDToolDefinition", "实际取到")
    assert_text_visible(page, "#threeDToolDefinition", "历史统计不代表")
    definition = page.locator("#threeDToolDefinition")
    assert definition.get_attribute("open") is None, "说明 must start collapsed"
    definition.locator("summary").click()
    page.wait_for_function(
        "() => document.querySelector('#threeDToolDefinition')?.open === true"
    )
    assert "开出前" in definition.inner_text()
    definition.locator("summary").click()
    page.wait_for_function(
        "() => document.querySelector('#threeDToolDefinition')?.open === false"
    )
    assert (
        page.locator('[data-three-d-window="30"]').get_attribute("aria-pressed") == "true"
    )
    rows = page.locator("#threeDTrendPanel table tbody tr").count()
    assert rows == 30, rows
    # The 遗漏 column used to be structurally 0 on every row of every draw. It now carries the
    # streak each drawn digit ended, so over 30 rows x 3 positions it cannot be a constant.
    omissions = page.evaluate(
        """
        () => Array.from(document.querySelectorAll("#threeDTrendPanel [data-digit-cell] span"))
          .map((node) => Number((node.textContent || "").replace("遗漏", "").trim()))
        """
    )
    assert len(omissions) == 90, len(omissions)
    assert all(value >= 0 for value in omissions), omissions
    assert max(omissions) > 0, omissions
    assert len(set(omissions)) > 1, omissions
    assert page.locator("#threeDToolHome").is_hidden()
    assert_no_page_horizontal_overflow(page)
    assert_matrix_scroll_contained(page)
    assert_not_loading_or_error(page)
    assert_tap_targets(page)


def measure_mobile_first_screen(page: Page) -> dict[str, Any]:
    """Measure the 390px first screen and assert the release bar.

    The bar: at scrollY 0 the draw status is fully visible and at least
    `MOBILE_FIRST_SCREEN_MIN_TOOLS` tool entries sit entirely above the fold. The numbers are
    both asserted here and reported into `design-qa.md`.
    """
    measured = page.evaluate(
        """
        () => {
          const fold = window.innerHeight;
          const box = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const rect = node.getBoundingClientRect();
            return {top: Math.round(rect.top), bottom: Math.round(rect.bottom), height: Math.round(rect.height)};
          };
          const band = document.querySelector("#threeDFreshness");
          const bandRect = band?.getBoundingClientRect();
          const tiles = Array.from(document.querySelectorAll("[data-three-d-tool-key]"));
          return {
            fold,
            scrollY: window.scrollY,
            statusFullyVisible: Boolean(bandRect && bandRect.top >= 0 && bandRect.bottom <= fold),
            statusBox: box("#threeDFreshness"),
            statusText: (band?.textContent || "").replace(/\\s+/g, " ").trim(),
            toolsAboveFold: tiles
              .filter((tile) => tile.getBoundingClientRect().bottom <= fold)
              .map((tile) => tile.dataset.threeDToolKey),
            firstToolTop: tiles.length
              ? Math.round(tiles[0].getBoundingClientRect().top)
              : null,
            chrome: {
              siteHeader: box(".site-header"),
              gameTabs: box("#gameTabs"),
              toolboxHead: box(".three-d-toolbox-head"),
              planStrip: box("#threeDPlanStrip"),
            },
          };
        }
        """
    )
    assert measured["scrollY"] == 0, measured
    assert len(page.locator("[data-three-d-tool-key]").all()) == len(TOOL_KEYS)
    measured["required_tools_above_fold"] = MOBILE_FIRST_SCREEN_MIN_TOOLS
    measured["meets_first_screen_bar"] = bool(
        measured["statusFullyVisible"]
        and len(measured["toolsAboveFold"]) >= MOBILE_FIRST_SCREEN_MIN_TOOLS
    )
    assert measured["statusFullyVisible"], measured
    assert len(measured["toolsAboveFold"]) >= MOBILE_FIRST_SCREEN_MIN_TOOLS, measured
    # The count must not have been bought by shrinking tiles below the touch floor.
    assert_tap_targets(page)
    return measured


def assert_tap_targets(page: Page) -> None:
    """Every visible control in the toolbox, button or link, keeps the 40px touch floor."""
    undersized = page.evaluate(
        """
        () => Array.from(
          document.querySelectorAll("#threeDToolbox button, #threeDToolbox a[href]"),
        )
          .filter((node) => node.offsetParent !== null)
          .map((node) => ({
            tag: node.tagName.toLowerCase(),
            label: (node.textContent || node.getAttribute("aria-label") || "").trim().slice(0, 20),
            height: Math.round(node.getBoundingClientRect().height),
          }))
          .filter((item) => item.height < 40)
        """
    )
    assert undersized == [], undersized


def screenshot_and_assert(
    page: Page,
    output: Path,
    viewport: dict[str, int],
    full_page: bool = True,
) -> dict[str, Any]:
    settle_for_screenshot(page)
    output.unlink(missing_ok=True)
    page.screenshot(path=str(output), full_page=full_page)
    width, height = png_size(output)
    assert width == viewport["width"], (output, width, viewport)
    if full_page:
        assert height >= viewport["height"], (output, height, viewport)
    else:
        # A first-screen capture is the fold itself: anything taller is not the first screen.
        assert height == viewport["height"], (output, height, viewport)
    assert output.stat().st_size > 10_000, (output, output.stat().st_size)
    display_path = output.relative_to(ROOT) if output.is_relative_to(ROOT) else Path(output.name)
    return {
        "file": str(display_path),
        "width": width,
        "height": height,
        "bytes": output.stat().st_size,
        "sha256": file_sha256(output),
    }


def settle_for_screenshot(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.evaluate(
        """
        async () => {
          if (document.fonts?.ready) await document.fonts.ready;
          await Promise.all(Array.from(document.images).map(async (image) => {
            if (!image.complete) {
              await new Promise((resolve) => {
                image.addEventListener("load", resolve, {once: true});
                image.addEventListener("error", resolve, {once: true});
              });
            }
            if (image.decode) await image.decode().catch(() => {});
          }));
          if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
          window.scrollTo(0, 0);
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }
        """
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    assert header.startswith(b"\x89PNG\r\n\x1a\n"), path
    return struct.unpack(">II", header[16:24])


def assert_text_visible(page: Page, selector: str, expected: str) -> None:
    locator = page.locator(selector).first
    locator.wait_for(state="visible", timeout=5000)
    text = locator.inner_text()
    assert expected in text, (selector, expected, text)


def assert_not_loading_or_error(page: Page) -> None:
    state = page.evaluate(
        """
        () => {
          const text = document.body.innerText;
          return {
            bodyLength: text.trim().length,
            loading: /加载中|读取中|正在读取|筛选中|保存中/.test(text),
            fatal: /暂时无法读取|数据加载失败|加载失败|LotteryProduct is unavailable|Internal Server Error/.test(text),
          };
        }
        """
    )
    assert state["bodyLength"] > 200, state
    assert state["loading"] is False, state
    assert state["fatal"] is False, state


def assert_no_page_horizontal_overflow(page: Page) -> None:
    overflow = page.evaluate(
        """
        () => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          bodyScrollWidth: document.body.scrollWidth,
          innerWidth: window.innerWidth,
        })
        """
    )
    assert overflow["scrollWidth"] <= overflow["clientWidth"] + 1, overflow
    assert overflow["bodyScrollWidth"] <= overflow["innerWidth"] + 1, overflow


def assert_text_not_clipped(page: Page, selectors: list[str]) -> None:
    clipped = page.evaluate(
        """
        (selectors) => selectors.flatMap((selector) => {
          return Array.from(document.querySelectorAll(selector)).map((node, index) => {
            const style = getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            if (
              style.display === "none" ||
              style.visibility === "hidden" ||
              rect.width <= 0 ||
              rect.height <= 0
            ) return null;
            return {
              selector: `${selector}[${index}]`,
              text: node.textContent.trim(),
              scrollWidth: node.scrollWidth,
              clientWidth: node.clientWidth,
              scrollHeight: node.scrollHeight,
              clientHeight: node.clientHeight,
            };
          }).filter(Boolean);
        }).filter((item) => {
          if (!item.text) return false;
          return item.scrollWidth > item.clientWidth + 2
            || item.scrollHeight > item.clientHeight + 2;
        })
        """,
        selectors,
    )
    assert clipped == [], clipped


def assert_no_key_overlap(page: Page, selectors: list[str]) -> None:
    overlaps = page.evaluate(
        """
        (selectors) => {
          const items = selectors.flatMap((selector) => {
            return Array.from(document.querySelectorAll(selector)).map((node, index) => {
              const style = getComputedStyle(node);
              const rect = node.getBoundingClientRect();
              if (
                style.display === "none" ||
                style.visibility === "hidden" ||
                Number(style.opacity) === 0 ||
                rect.width <= 0 ||
                rect.height <= 0
              ) return null;
              return {selector, index, node, rect};
            }).filter(Boolean);
          });
          const hits = [];
          for (let i = 0; i < items.length; i += 1) {
            for (let j = i + 1; j < items.length; j += 1) {
              const a = items[i];
              const b = items[j];
              if (a.node.contains(b.node) || b.node.contains(a.node)) continue;
              const x = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
              const y = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
              if (x > 1 && y > 1) {
                hits.push([
                  `${a.selector}[${a.index}]`,
                  `${b.selector}[${b.index}]`,
                  Math.round(x),
                  Math.round(y),
                ]);
              }
            }
          }
          return hits;
        }
        """,
        selectors,
    )
    assert overlaps == [], overlaps


def assert_cta_not_covered(page: Page, selector: str) -> None:
    page.locator(selector).scroll_into_view_if_needed()
    covered = page.evaluate(
        """
        (selector) => {
          const node = document.querySelector(selector);
          if (!node) return {selector, missing: true};
          const rect = node.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) return {selector, hidden: true};
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          const top = document.elementFromPoint(x, y);
          return {
            selector,
            top: top ? `${top.tagName.toLowerCase()}#${top.id}.${top.className}` : "",
            ok: top === node || node.contains(top) || top?.contains(node),
          };
        }
        """,
        selector,
    )
    assert covered.get("ok") is True, covered


def assert_matrix_scroll_contained(page: Page) -> None:
    result = page.evaluate(
        """
        () => Array.from(document.querySelectorAll(".three-d-scroll"))
          .filter((node) => node.offsetParent !== null)
          .map((node) => {
            const style = getComputedStyle(node);
            return {
              id: node.id,
              scrollWidth: node.scrollWidth,
              clientWidth: node.clientWidth,
              overflowX: style.overflowX,
            };
          })
        """
    )
    assert result, result
    for item in result:
        if item["scrollWidth"] > item["clientWidth"] + 1:
            assert item["overflowX"] in {"auto", "scroll"}, item


if __name__ == "__main__":
    main()
