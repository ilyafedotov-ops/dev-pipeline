from pathlib import Path

from tasksgodzilla import pipeline


def test_step_markdown_files_filters_and_sorts(tmp_path: Path) -> None:
    filenames = [
        "plan.md",
        "context.md",
        "log.md",
        "notes.md",
        "00-setup.md",
        "02-b.md",
        "01-a.md",
        "README.md",
    ]
    for name in filenames:
        (tmp_path / name).write_text(name, encoding="utf-8")

    steps = pipeline.step_markdown_files(tmp_path)
    assert [p.name for p in steps] == ["01-a.md", "02-b.md"]

    steps_with_setup = pipeline.step_markdown_files(tmp_path, include_setup=True)
    assert [p.name for p in steps_with_setup] == ["00-setup.md", "01-a.md", "02-b.md"]
