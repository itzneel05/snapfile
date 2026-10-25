"""Tests for the model-output parser and filing math (no model needed)."""

import pytest

from snapfile.client import LocalModelError, parse_json_object
from snapfile.filer import Shot, plan_destination, slugify


def test_parse_plain_json():
    assert parse_json_object('{"kind": "ui", "keep": true}') == {"kind": "ui", "keep": True}


def test_parse_fenced_json():
    text = 'Sure!\n```json\n{"kind": "meme"}\n```\n'
    assert parse_json_object(text) == {"kind": "meme"}


def test_parse_json_wrapped_in_prose():
    text = 'Here you go: {"kind": "doc", "title": "quarterly report"} hope that helps'
    assert parse_json_object(text)["kind"] == "doc"


def test_parse_braces_inside_string():
    text = '{"title": "stack trace {with braces}", "kind": "code-error"}'
    assert parse_json_object(text)["kind"] == "code-error"


def test_parse_garbage_raises():
    with pytest.raises(LocalModelError):
        parse_json_object("no json here at all")


def test_slugify_basic():
    assert slugify("Nginx 404 Not Found!") == "nginx-404-not-found"
    assert slugify("  ") == ""


def test_plan_destination_no_collision(tmp_path):
    shot = Shot(path=tmp_path / "old.png", title="Login screen redesign", kind="ui")
    dest = plan_destination(shot, tmp_path / "sorted")
    assert dest == tmp_path / "sorted" / "ui" / "login-screen-redesign.png"


def test_plan_destination_avoids_existing(tmp_path):
    out = tmp_path / "sorted" / "ui"
    out.mkdir(parents=True)
    (out / "login-screen-redesign.png").touch()
    shot = Shot(path=tmp_path / "old.png", title="Login screen redesign", kind="ui")
    dest = plan_destination(shot, tmp_path / "sorted")
    assert dest.name == "login-screen-redesign-1.png"
