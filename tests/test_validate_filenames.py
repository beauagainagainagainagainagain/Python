import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_filenames


def test_validate_filenames_main_all_good(monkeypatch):
    monkeypatch.setattr(
        validate_filenames,
        "good_file_paths",
        lambda: iter(["foo/bar.py", "baz/qux.py"]),
    )
    assert validate_filenames.main() == 0


def test_validate_filenames_main_reports_issues(monkeypatch, capsys):
    monkeypatch.setattr(
        validate_filenames,
        "good_file_paths",
        lambda: iter(["Foo/bar.py", "bad name.py", "bad-hyphen/file.py", "top.py"]),
    )
    result = validate_filenames.main()
    captured = capsys.readouterr().out
    assert result == 5
    assert "uppercase" in captured
    assert "space" in captured
    assert "hyphen" in captured
    assert "not in a directory" in captured
