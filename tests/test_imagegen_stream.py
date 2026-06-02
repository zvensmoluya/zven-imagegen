from __future__ import annotations

import base64
import importlib.util
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "zven-imagegen" / "scripts" / "imagegen_stream.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("imagegen_stream", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def tiny_png() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")


def test_parse_dotenv_accepts_export_and_quotes(tmp_path: Path) -> None:
    helper = load_helper()
    env_file = tmp_path / ".imagegen.env"
    env_file.write_text(
        "\n".join(
            [
                "# ignored",
                'export IMAGEGEN_OPENAI_API_KEY="secret"',
                "IMAGEGEN_OPENAI_BASE_URL='https://example.test/openai'",
            ]
        ),
        encoding="utf-8",
    )

    values = helper.parse_dotenv(env_file)

    assert values["IMAGEGEN_OPENAI_API_KEY"] == "secret"
    assert values["IMAGEGEN_OPENAI_BASE_URL"] == "https://example.test/openai"


def test_normalize_base_url_appends_v1_once() -> None:
    helper = load_helper()

    assert helper.normalize_base_url("https://example.test") == "https://example.test/v1"
    assert helper.normalize_base_url("https://example.test/v1") == "https://example.test/v1"
    assert helper.normalize_base_url(None) is None


def test_collect_b64_images_from_completion_shapes() -> None:
    helper = load_helper()

    assert helper.collect_b64_images({"b64_json": "one"}) == ["one"]
    assert helper.collect_b64_images({"data": [{"b64_json": "one"}, {"image_b64": "two"}]}) == [
        "one",
        "two",
    ]
    assert helper.collect_b64_images(SimpleNamespace(data=[SimpleNamespace(b64_json="one")])) == [
        "one"
    ]


def test_consume_stream_collects_completed_events(capsys: object) -> None:
    helper = load_helper()
    events = [
        {"type": "image_generation.partial_image", "partial_image_index": 0},
        {"type": "image_generation.completed", "b64_json": "final"},
    ]

    images = helper.consume_stream(events, label="[test]")

    assert images == ["final"]
    stderr = capsys.readouterr().err
    assert "partial image 0 received" in stderr
    assert "completed" in stderr


def test_consume_stream_uses_latest_partial_without_completed(capsys: object) -> None:
    helper = load_helper()
    events = [
        {"type": "image_generation.partial_image", "partial_image_index": 0, "b64_json": "draft"},
        {"type": "image_generation.partial_image", "partial_image_index": 1, "b64_json": "finalish"},
    ]

    images = helper.consume_stream(events, label="[test]")

    assert images == ["finalish"]
    stderr = capsys.readouterr().err
    assert "partial image 1 received" in stderr
    assert "without a completed event" in stderr


def test_consume_stream_accepts_typeless_sdk_image_events(capsys: object) -> None:
    helper = load_helper()
    events = [
        SimpleNamespace(type=None, b64_json="draft", partial_image_index=None),
        SimpleNamespace(type=None, b64_json="finalish", partial_image_index=None),
    ]

    images = helper.consume_stream(events, label="[test]")

    assert images == ["finalish"]
    stderr = capsys.readouterr().err
    assert "partial image" in stderr
    assert "without a completed event" in stderr


def test_consume_stream_keeps_latest_partial_per_output(capsys: object) -> None:
    helper = load_helper()
    events = [
        {
            "type": "image_generation.partial_image",
            "image_index": 0,
            "partial_image_index": 0,
            "b64_json": "first-draft",
        },
        {
            "type": "image_generation.partial_image",
            "image_index": 1,
            "partial_image_index": 0,
            "b64_json": "second-finalish",
        },
        {
            "type": "image_generation.partial_image",
            "image_index": 0,
            "partial_image_index": 1,
            "b64_json": "first-finalish",
        },
    ]

    images = helper.consume_stream(events, label="[test]")

    assert images == ["first-finalish", "second-finalish"]
    assert "without a completed event" in capsys.readouterr().err


def test_write_images_expands_single_output_path(tmp_path: Path) -> None:
    helper = load_helper()
    image = base64.b64encode(tiny_png()).decode("ascii")
    output = tmp_path / "asset.png"

    helper.write_images([image, image], [output], force=False)

    assert (tmp_path / "asset-01.png").read_bytes() == tiny_png()
    assert (tmp_path / "asset-02.png").read_bytes() == tiny_png()


def test_write_images_accepts_data_uri_png(tmp_path: Path) -> None:
    helper = load_helper()
    image = "data:image/png;base64," + base64.b64encode(tiny_png()).decode("ascii")
    output = tmp_path / "asset.png"

    helper.write_images([image], [output], force=False)

    assert output.read_bytes() == tiny_png()


def test_write_images_rejects_invalid_png(tmp_path: Path) -> None:
    helper = load_helper()
    bad = base64.b64encode(b"\x89PNG\r\n\x1a\nnot-a-valid-png").decode("ascii")

    try:
        helper.write_images([bad], [tmp_path / "bad.png"], force=False)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("write_images should reject invalid PNG data")

    assert not (tmp_path / "bad.png").exists()
