from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "zven-imagegen" / "scripts" / "imagegen_stream.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("imagegen_stream", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_write_images_expands_single_output_path(tmp_path: Path) -> None:
    helper = load_helper()
    image = base64.b64encode(b"png-bytes").decode("ascii")
    output = tmp_path / "asset.png"

    helper.write_images([image, image], [output], force=False)

    assert (tmp_path / "asset-01.png").read_bytes() == b"png-bytes"
    assert (tmp_path / "asset-02.png").read_bytes() == b"png-bytes"
