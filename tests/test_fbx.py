from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# from fbx import from_moz_date, get_opts, main
import fbx


def moz_date(days: int) -> int:
    base_date: datetime = datetime(2023, 1, 2, 3, 4, 5)
    d = base_date + timedelta(days=days)
    #  Convert to milliseconds.
    return d.timestamp() * 1000000.0


def test_moz_date():
    md = moz_date(0)
    assert fbx.from_moz_date(md) == "2023-01-02 03:04:05"
    md = moz_date(-1)
    assert fbx.from_moz_date(md) == "2023-01-01 03:04:05"
    md = moz_date(1)
    assert fbx.from_moz_date(md) == "2023-01-03 03:04:05"


def make_fake_places_file(file_path: Path):
    assert not file_path.exists(), "Should be a new file."

    con = sqlite3.connect(str(file_path))
    cur = con.cursor()

    cur.execute("CREATE TABLE moz_places (id INTEGER, url TEXT);")

    cur.execute(
        "CREATE TABLE moz_bookmarks (id INTEGER, fk INTEGER, title TEXT, "
        "parent INTEGER, dateAdded INTEGER);"
    )

    #  Insert places (URLs).
    cur.execute("INSERT INTO moz_places VALUES (?, ?);", (1, "http://www.example.com/"))

    cur.execute(
        "INSERT INTO moz_places VALUES (?, ?);",
        (2, "http://www.example.com/page1"),
    )

    cur.execute(
        "INSERT INTO moz_places VALUES (?, ?);",
        (3, "http://www.example.com/page2"),
    )
    #  moz_places: id, url

    #  Insert entries for menu and folders.
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (1, None, "menu", 0, moz_date(0)),
    )
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (2, None, "folder-1", 1, moz_date(0)),
    )
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (3, None, "folder-2", 1, moz_date(0)),
    )
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (4, None, "folder-2a", 3, moz_date(0)),
    )

    #  Insert entries for bookmarked places.
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (5, 1, "Example Home Page", 2, moz_date(0)),
    )
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (6, 2, "Example Page 1", 3, moz_date(4)),
    )
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (7, 3, "Example Page 2", 4, moz_date(2)),
    )

    #  moz_bookmarks: id, fk, title, parent, dateAdded

    con.commit()
    con.close()


@pytest.fixture()
def setup_tmp_source_and_output(tmp_path) -> tuple[Path, Path]:
    """
    Creates a fake (well, it's a real sqlite db) places.sqlite to
    simulate one created by Firefox, but with only the fields
    queried by fbx.py.

    Returns a tuple of (src_file, out_dir) where src_file is the
    places.sqlite file and out_dir is the location where output
    files should be written. Both are pathlib.Path objects.
    """
    src_dir = tmp_path / "profile"
    src_dir.mkdir()
    src_file = src_dir / "places.sqlite"
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    make_fake_places_file(src_file)
    return (src_file, out_dir)


def test_opt_default_profile():
    args = []
    opts = fbx.get_opts(args)
    print(f"\n{opts}")
    assert opts.places_file, (
        "This will fail if there is no Firefox profile found on the host in "
        "the expected location. Either the expected location is wrong, or "
        "Firefox is not installed (or Mozilla changed their data file name)."
    )
    assert isinstance(opts.output_file, Path)


def test_opt_profile(tmp_path: Path):
    p1 = tmp_path.joinpath("profileZ")
    p1.mkdir()
    p1 = p1.joinpath("places.sqlite")
    print(f"\n{p1}")
    make_fake_places_file(p1)

    #  profile2 will have the newer file.
    p2 = tmp_path.joinpath("profileA")
    p2.mkdir()
    p2 = p2.joinpath("places.sqlite")
    print(f"\n{p2}")
    make_fake_places_file(p2)

    args = ["--profile", str(tmp_path)]
    opts = fbx.get_opts(args)
    assert str(p2) == str(opts.places_file), (
        "Should pick the profile with the most recent places.sqlite file when "
        "given a parent of the profile location."
    )


def test_opt_places_file(tmp_path: Path):
    p1 = tmp_path.joinpath("profile1")
    p1.mkdir()
    p1 = p1.joinpath("places.sqlite")
    print(f"\n{p1}")
    make_fake_places_file(p1)

    #  profile2 will have the newer file.
    p2 = tmp_path.joinpath("profile2")
    p2.mkdir()
    p2 = p2.joinpath("places.sqlite")
    print(f"\n{p2}")
    make_fake_places_file(p2)

    args = ["--profile", str(p2.parent), "--places-file", str(p1)]
    opts = fbx.get_opts(args)
    assert str(p1) == str(opts.places_file), "--places-file should override --profile"


def test_opt_default_output():
    args = []
    opts = fbx.get_opts(args)
    print(f"\n{opts}")
    assert isinstance(opts.output_file, Path)
    assert "Desktop" in str(opts.output_file)


def test_opt_output_name():
    args = ["--output-name", "myname.txt"]
    opts = fbx.get_opts(args)
    print(f"\n{opts}")
    assert opts.output_file.name == "myname.html", (
        "File name suffix should always be '.html'."
    )


def test_opt_md_output_names():
    args = ["--output-name", "myname.txt", "--by-date", "--md"]
    opts = fbx.get_opts(args)
    print(f"\n{opts}")
    assert opts.md_file.name == "myname.md"
    assert opts.md_bydate.name == "myname-bydate.md"


def test_opt_output_folder(tmp_path):
    args = ["--output-folder", str(tmp_path)]
    opts = fbx.get_opts(args)
    print(f"\n{opts}")
    assert str(opts.output_file.parent) == str(tmp_path), (
        "Output file should be in specified folder."
    )


def test_html_output(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        "test-fbx-output.html",
        "--by-date",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    assert (out_dir / "test-fbx-output.html").exists()
    assert (out_dir / "test-fbx-output-bydate.html").exists()


def test_html_output_w_copy(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    cp_dir = out_dir / "copy"
    cp_dir.mkdir()
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        "test-fbx-output.html",
        "--by-date",
        "--cp-dir",
        str(cp_dir),
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    assert (cp_dir / "test-fbx-output.html").exists()
    assert (cp_dir / "test-fbx-output-bydate.html").exists()


def test_html_output_w_copy_dest_missing(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    cp_dir = out_dir / "copy"
    #  cp_dir.mkdir()  # Do not create the directory.
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        "test-fbx-output.html",
        "--by-date",
        "--cp-dir",
        str(cp_dir),
    ]
    with pytest.raises(SystemExit):
        result = fbx.main(args)
        assert result == 1
    captured = capsys.readouterr()
    assert "ERROR: Cannot find folder" in captured.err


def test_markdown_output(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    out_name = "test-fbx-output.md"
    out_md = out_dir / out_name
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        out_name,
        "--md",
        "--by-date",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    assert out_md.exists()
    assert (out_dir / "test-fbx-output-bydate.md").exists()


def test_markdown_output_w_copy(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    cp_dir = out_dir / "copy"
    cp_dir.mkdir()
    out_name = "test-fbx-output.md"
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        out_name,
        "--md",
        "--by-date",
        "--cp-dir",
        str(cp_dir),
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    assert (cp_dir / "test-fbx-output.md").exists()
    assert (cp_dir / "test-fbx-output-bydate.md").exists()


def test_csv_output(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    out_name = "test-fbx-output.csv"
    out_csv = out_dir / out_name
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-name",
        out_name,
        "--csv",
        "--by-date",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    assert out_csv.exists()
    assert (out_dir / "test-fbx-output.csv").exists()


def test_outputs_w_rm_prev(setup_tmp_source_and_output, capsys, monkeypatch):
    def fake_get_asof_date(use_mtime: bool, places_file: Path, counter=[0]) -> datetime:  # noqa: B006
        #  The counter default argument is a mutable list that is initialized
        #  when the function is defined. The list persists between calls, therefore it
        #  can be incremented and the value will be retained between calls.
        #  This is a way to simulate a changing date-time value for testing.
        counter[0] += 1
        return datetime(2025, 1, 2, 3, counter[0], 5)

    monkeypatch.setattr("fbx.get_asof_date", fake_get_asof_date)

    src_file, out_dir = setup_tmp_source_and_output
    cp_dir = out_dir / "copy"
    cp_dir.mkdir()
    # out_name = "test-fbx-output.md"
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--host-name",
        "test_host",
        "--md",
        "--by-date",
        "--cp-dir",
        str(cp_dir),
        "--rm-prev",
        "--csv",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    out_files = [x for x in out_dir.glob("*") if x.is_file()]
    assert len(out_files) == 5
    cp_files = list(cp_dir.glob("*"))
    assert len(cp_files) == 5

    # Run again with the same options. The '--rm-prev' option should cause
    # the previous output files to be removed.

    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    out_files = [x for x in out_dir.glob("*") if x.is_file()]
    assert len(out_files) == 5
    cp_files = list(cp_dir.glob("*"))
    assert len(cp_files) == 5


def test_db_output(setup_tmp_source_and_output, capsys):
    #  Maybe this test does too much, but it seems to make sense to chain
    #  these operations instead of fiddling with a bunch of extra setup just
    #  to make a test only test one thing. So says the impurist. :}~

    src_file, out_dir = setup_tmp_source_and_output

    #  Read a places.sqlite file and write to a sqlite database.
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-sqlite=test-fbx-db-output.sqlite",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out

    #  Read the same places.sqlite file and write to the same sqlite database.
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-sqlite=test-fbx-db-output.sqlite",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 1
    assert " already in " in captured.out, "Should not load duplicate data."

    #  Read the same places.sqlite file and write to the same sqlite database,
    #  but say it's from a different host (--host-name parameter).
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--output-sqlite=test-fbx-db-output.sqlite",
        "--host-name=other_host",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out

    #  Read the sqlite database and write HTML files.
    args = [
        "--output-folder",
        str(out_dir),
        f"--from-sqlite={out_dir}/test-fbx-db-output.sqlite",
        "--output-name",
        "test-fbx-output-from-db.html",
        "--by-date",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out

    html_path = out_dir / "test-fbx-output-from-db.html"
    assert html_path.exists()
    assert "other_host" in html_path.read_text()


def test_use_places_file_timestamp(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output

    # Set a specific timestamp on the test places.sqlite file.
    dt = datetime(2023, 1, 2, 3, 4, 5)
    ts = dt.timestamp()
    os.utime(src_file, (ts, ts))

    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        "--asof-mtime",
    ]
    result = fbx.main(args)

    captured = capsys.readouterr()

    assert result == 0
    assert "Done." in captured.out

    files = list(out_dir.glob("*.html"))
    assert len(files) == 1
    out_file = files[0]

    # Should get 'as of' date-time from the places.file last modified
    # timestamp when the '--asof-mtime' option is used.
    assert f"{dt.strftime('%y%m%d_%H%M')}" in out_file.name
    assert f" as of {dt.strftime('%Y-%m-%d %H:%M')}" in out_file.read_text()


def get_db_table_row_count(db_path: Path, table_name: str) -> int:
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name};")  # noqa: S608
    n_rows = cur.fetchone()[0]
    cur.close()
    con.close()
    return n_rows


def test_get_db_row_count(setup_tmp_source_and_output):
    src_file, _ = setup_tmp_source_and_output
    n_rows = get_db_table_row_count(src_file, "moz_bookmarks")
    assert n_rows == 7


def test_db_output_update_by_host(setup_tmp_source_and_output, capsys):
    src_file, out_dir = setup_tmp_source_and_output
    out_db = out_dir / "test-fbx-db-output.sqlite"

    #  Read a places.sqlite file and write to a sqlite database.
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        f"--output-sqlite={out_db.name}",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out

    n_rows = get_db_table_row_count(out_db, "bookmarks")
    assert n_rows == 3

    #  Read the same places.sqlite file and write to the same sqlite database,
    #  but say it's from a different host (--host-name parameter).
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        f"--output-sqlite={out_db.name}",
        "--host-name=other_host",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    n_rows = get_db_table_row_count(out_db, "bookmarks")
    assert n_rows == 6

    #  Add a new bookmark to the source.
    con = sqlite3.connect(str(src_file))
    cur = con.cursor()
    #  moz_places: id, url
    cur.execute(
        "INSERT INTO moz_places VALUES (?, ?);",
        (4, "http://www.example.com/page3"),
    )
    #  moz_bookmarks: id, fk, title, parent, dateAdded
    cur.execute(
        "INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?);",
        (7, 4, "Example Page 3", 4, moz_date(3)),
    )
    con.commit()
    cur.close()
    con.close()

    #  Read the updated places.sqlite file and write to the same sqlite database,
    #  as 'other_host' using the '--update' option.
    args = [
        "--places-file",
        str(src_file),
        "--output-folder",
        str(out_dir),
        f"--output-sqlite={out_db.name}",
        "--host-name=other_host",
        "--update",
    ]
    result = fbx.main(args)
    captured = capsys.readouterr()
    assert result == 0
    assert "Done." in captured.out
    n_rows = get_db_table_row_count(out_db, "bookmarks")
    assert n_rows == 7
