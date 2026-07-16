from __future__ import annotations

from pneural_context.pb_dashboard import render_dashboard


def test_render_dashboard_empty_project():
    html = render_dashboard()
    assert "<!DOCTYPE html>" in html
    assert "JSON.parse" in html
    assert "pneural-context Dashboard" in html


def test_render_dashboard_with_project():
    html = render_dashboard("my-project")
    assert "my-project" in html
    assert "JSON.parse" in html


def test_render_dashboard_xss_protection():
    html = render_dashboard("<script>alert(1)</script>")
    script_count = html.count("<script>")
    assert script_count == 1  # only the legitimate script tag


def test_render_dashboard_caches_template():
    html1 = render_dashboard("test1")
    html2 = render_dashboard("test2")
    assert "test1" in html1
    assert "test2" in html2
    assert "test1" not in html2


def test_render_dashboard_special_chars():
    html = render_dashboard('test "quotes" & <angles>')
    assert "JSON.parse" in html
    assert "\\x3c" in html or "\\x3e" in html
