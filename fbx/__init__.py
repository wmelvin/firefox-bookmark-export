#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent, indent
from typing import NamedTuple

app_name = "fbx.py"

__version__ = "2025.05.1"

app_title = f"{app_name} (v{__version__})"

run_dt = datetime.now()


class AppOptions(NamedTuple):
    places_file: Path
    output_file: Path
    bydate_file: Path
    md_file: Path
    md_bydate: Path
    out_db: Path
    in_db: Path
    host_name: str
    use_mtime: bool
    do_update: bool
    cp_dir: Path
    base_name: str
    rm_prev: bool


class Bookmark(NamedTuple):
    title: str
    url: str
    parent_path: str
    when_added: str
    host_name: str
    asof_dt: str


def get_args(arglist=None):
    ap = argparse.ArgumentParser(
        description="Exports Firefox bookmarks to a single HTML file."
    )

    ap.add_argument(
        "--profile",
        dest="profile",
        action="store",
        help="Path to the Firefox profile folder.",
    )

    ap.add_argument(
        "--places-file",
        dest="places_file",
        action="store",
        help="Path to a specific version of the 'places.sqlite' file. "
        "Overrides the '--profile' options.",
    )

    ap.add_argument(
        "--asof-mtime",
        dest="use_mtime",
        action="store_true",
        help="Use the modified time of the 'places.sqlite' file for the 'as of' "
        "date-time listed in the output files.",
    )

    ap.add_argument(
        "--output-name",
        dest="output_file",
        action="store",
        help="Name of the output HTML file.",
    )

    ap.add_argument(
        "--output-folder",
        dest="output_folder",
        action="store",
        help="Name of the folder in which to create the output HTML file.",
    )

    ap.add_argument(
        "--by-date",
        dest="do_bydate",
        action="store_true",
        help="Also produce an output file listing bookmarks by date-added "
        "(most recent first). The name of the output file will be the same "
        "as the main output file with '-bydate' added to the file name.",
    )

    ap.add_argument(
        "--md",
        dest="do_markdown",
        action="store_true",
        help="Also produce a Markdown file listing the bookmarks "
        "The name of the output file will be the same as the HTML output "
        "file with a '.md' suffix. If the --by-date switch is used, a "
        "separate Markdown file by date (oldest first) is produced.",
    )

    ap.add_argument(
        "--output-sqlite",
        dest="output_db",
        action="store",
        help="Name of the SQLite database file to produce instead of HTML "
        "files. This overrides the --output-name and --by-date options, "
        "but still uses the --output-folder option. If the database file "
        "already exists, new data is appended (but only if from a "
        "different host).",
    )

    ap.add_argument(
        "--host-name",
        dest="host_name",
        action="store",
        help="Use a specified host name, instead of the current machine's "
        "host name. This is useful when reading data from a copy of a "
        "'places.sqlite' file taken from another machine.",
    )

    ap.add_argument(
        "--update",
        dest="do_update",
        action="store_true",
        help="Update SQLite output database with the data from the specified "
        "'places.sqlite' file. This is required if you want to insert "
        "(replace) data from a host that is already in the database.",
    )

    ap.add_argument(
        "--from-sqlite",
        dest="source_db",
        action="store",
        help="Name of a SQLite database, previously created by {0}, from "
        "which to get the list of bookmarks for producing the HTML output "
        "files. This must be the full path to the file (unless it is in "
        "the current directory)".format(app_name),
    )

    ap.add_argument(
        "--cp-dir",
        dest="cp_dir",
        action="store",
        help="Write a second copy the output files to the specified directory. "
        "Only applies to HTML and Markdown files.",
    )

    ap.add_argument(
        "--rm-prev",
        dest="rm_prev",
        action="store_true",
        help="Remove previous output files in the output folder. "
        "Only applies to HTML and Markdown files.",
    )

    return ap.parse_args(arglist)


def get_opts(arglist=None):  # noqa: PLR0912, PLR0915
    args = get_args(arglist)

    if args.source_db:
        in_db = Path(args.source_db)
        if not in_db.exists():
            sys.stderr.write(f"\nERROR: Cannot find '{in_db}'\n")
            sys.exit(1)
    else:
        in_db = None

    places_file = None

    #  If the '--from-sqlite' option is used to read data from an existing
    #  database created by fbx, no Firefox places file is needed.
    #  Otherwise, get the path to the places file.
    if in_db is None:
        if args.places_file:
            places_file = Path(args.places_file)
        else:
            if args.profile:
                p = Path(args.profile)
            else:
                windows_appdata = os.getenv("APPDATA")
                if windows_appdata:
                    p = Path(windows_appdata) / "Mozilla" / "Firefox" / "Profiles"
                else:
                    p = Path("~/.mozilla/firefox").expanduser().resolve()

            if not p.exists():
                sys.stderr.write(f"\nERROR: Cannot find folder '{p}'\n")
                sys.exit(1)

            files = list(p.glob("**/places.sqlite"))
            files.sort(key=lambda x: x.stat().st_mtime)
            places_file = files[-1]

        if places_file:
            if not places_file.exists():
                sys.stderr.write(f"\nERROR: Cannot find folder '{p}'\n")
                sys.exit(1)
        else:
            sys.stderr.write("\nERROR: No profile or file name specified.'\n")
            sys.exit(1)

    if args.output_folder:
        out_dir = Path(args.output_folder).expanduser().resolve()
    else:
        out_dir = Path.home().joinpath("Desktop")

    if args.output_db:
        out_db = Path(args.output_db)
        out_db = Path(out_db.stem).with_suffix(".sqlite")
        if not out_db.is_absolute():
            out_db = out_dir.joinpath(out_db.name)
    else:
        out_db = None

    host_name = args.host_name if args.host_name else socket.gethostname()

    if args.output_file:
        out_file = Path(args.output_file)
        base_name = out_file.stem
        out_file = Path(base_name).with_suffix(".html")
    else:
        dt_tag = get_asof_date(args.use_mtime, places_file).strftime("%y%m%d_%H%M")
        base_name = f"Firefox-bookmarks-{host_name}-"
        out_file = Path(f"{base_name}{dt_tag}.html")

    output_file = out_dir.joinpath(out_file.name)

    if args.do_bydate:
        bydate_file = output_file.parent.joinpath(
            f"{output_file.stem}-bydate{output_file.suffix}"
        )
    else:
        bydate_file = None

    md_file = None
    md_bydate = None
    if args.do_markdown:
        md_file = output_file.parent.joinpath(f"{output_file.stem}.md")
        if bydate_file:
            md_bydate = bydate_file.parent.joinpath(f"{bydate_file.stem}.md")

    if args.cp_dir:
        cp_dir = Path(args.cp_dir).expanduser().resolve()
        if not cp_dir.exists():
            sys.stderr.write(f"\nERROR: Cannot find folder '{cp_dir}'\n")
            sys.exit(1)
    else:
        cp_dir = None

    return AppOptions(
        places_file,
        output_file,
        bydate_file,
        md_file,
        md_bydate,
        out_db,
        in_db,
        host_name,
        args.use_mtime,
        args.do_update,
        cp_dir,
        base_name,
        args.rm_prev,
    )


def html_style():
    s = """
        body {
            background-color: oldlace;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 1rem 4rem;
        }
        a:link, a:visited {
            color: #00248F;
            text-decoration: none;
        }
        :link:hover,:visited:hover {
            color: #B32400;
            text-decoration: underline;
        }
        .bookmark-path { color: gray; }
        .bookmark-title { color: black; }
        .added-dt {
            color: darkslateblue;
            font-size: 12px;
        }
        .asof {
            color: brown;
            font-size: 18px;
            font-weight: bold;
            margin-top: 2rem;
        }
        #footer {
            border-top: 1px solid black;
            font-size: x-small;
            margin-top: 2rem;
        }
    """
    return s.lstrip("\n").rstrip()


def html_head(title):
    return (
        dedent(
            """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta name="generator" content="{0}">
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
            <title>{1}</title>
            <style>
        {2}
            </style>
            <base target="_blank">
        </head>
        <body>
        <h1>{1}</h1>
        <ul>
        """
        )
        .format(app_name, title, html_style())
        .strip("\n")
    )


def html_tail():
    return dedent(
        """
        </ul>
        <div id="footer">
          Created {0} by {1}.
        </div>
        </body>
        </html>
        """
    ).format(run_dt.strftime("%Y-%m-%d %H:%M"), app_title)


def limited(value):
    length_limit = 180
    s = str(value)
    if len(s) <= length_limit:
        return s
    return s[:177] + "..."


def htm_txt(text: str) -> str:
    s = text.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    return s.replace(">", "&gt;")


def htm_url(url: str) -> str:
    return url.replace("&", "%26")


def write_bookmarks_html(html_file: Path, bmks: list[Bookmark], cp_dir: Path):
    print(f"Writing '{html_file}'")

    #  https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts
    bmks.sort(key=lambda item: item.title.lower())
    bmks.sort(key=lambda item: item.parent_path.lower())
    bmks.sort(key=lambda item: item.host_name.lower())

    with html_file.open("w", encoding="utf-8") as f:
        f.write(html_head("Bookmarks"))

        last_host = ""

        for bmk in bmks:
            assert bmk.host_name  # noqa: S101
            assert bmk.asof_dt  # noqa: S101

            if bmk.host_name != last_host:
                f.write(
                    f"<div class=\"asof\">On host '{bmk.host_name}' "
                    f"as of {bmk.asof_dt}</div>\n"
                )
                last_host = bmk.host_name

            title = bmk.title.strip()
            s = dedent(
                """
                    <li>
                        <p>
                        <span class="bookmark-title">{1}</span><br />
                        <span class="bookmark-path">{0}</span><br />
                        <a href="{2}">{2}</a><br />
                        <span class="added-dt">Added {3}</span>
                        </p>
                    </li>
                    """
            ).format(
                htm_txt(bmk.parent_path),
                htm_txt(title),
                htm_url(bmk.url),
                bmk.when_added,
            )
            f.write(indent(s, " " * 8))
        f.write(html_tail())
    if cp_dir:
        cp_file = cp_dir / html_file.name
        print(f"Copying to '{cp_file}'")
        cp_file.write_text(html_file.read_text())


def write_bookmarks_by_date_html(
    html_file: Path, n_hosts: int, bmks: list[Bookmark], cp_dir: Path
):
    print(f"Writing '{html_file}'")

    #  Re-sort bookmarks list.
    bmks.sort(key=lambda item: item.host_name.lower())
    bmks.sort(key=lambda item: item.url)
    bmks.sort(key=lambda item: item.when_added, reverse=True)

    with html_file.open("w") as f:
        f.write(html_head("Bookmarks by Date Added"))

        if n_hosts > 1:
            f.write('<div class="asof">\n')
            f.write("Combined bookmarks from multiple hosts.\n</div>\n")
        elif bmks:
            f.write(
                f'<div class="asof">On host {bmks[0].host_name} '
                f"as of {bmks[0].asof_dt}</div>\n"
            )

        host_str = ""

        for bmk in bmks:
            if n_hosts > 1:
                host_str = f"&nbsp;&nbsp;&nbsp;({bmk.host_name})"

            title = limited(ascii(bmk.title))
            s = dedent(
                """
                    <li>
                        <p>
                        <span class="bookmark-title">{1}</span><br />
                        <span class="bookmark-path">{0}</span><br />
                        <a href="{2}">{2}</a><br />
                        <span class="added-dt">Added {3}{4}</span>
                        </p>
                    </li>
                    """
            ).format(
                htm_txt(bmk.parent_path),
                htm_txt(title),
                htm_url(bmk.url),
                bmk.when_added,
                host_str,
            )
            f.write(indent(s, " " * 8))
        f.write(html_tail())
    if cp_dir:
        cp_file = cp_dir / html_file.name
        print(f"Copying to '{cp_file}'")
        cp_file.write_text(html_file.read_text())


def write_bookmarks_markdown(md_file: Path, bmks: list[Bookmark], cp_dir: Path):
    print(f"Writing '{md_file}'")

    bmks.sort(key=lambda item: item.title.lower())
    bmks.sort(key=lambda item: item.parent_path.lower())
    bmks.sort(key=lambda item: item.host_name.lower())

    with md_file.open("w") as f:
        f.write("# Bookmarks\n\n")

        last_host = ""

        for bmk in bmks:
            if bmk.host_name != last_host:
                f.write(f"On host **{bmk.host_name}** as of **{bmk.asof_dt}**\n\n")
                last_host = bmk.host_name

            title = limited(ascii(bmk.title)).strip("'")

            f.write(
                f"[{htm_txt(title)}]({htm_url(bmk.url)})\n"
                f"Added: `{bmk.when_added}`\n"
                f"Folder: `{htm_txt(bmk.parent_path)}`\n\n"
            )

        f.write(
            "---\n\nCreated {0} by {1}".format(
                run_dt.strftime("%Y-%m-%d %H:%M"), app_title
            )
        )
    if cp_dir:
        cp_file = cp_dir / md_file.name
        print(f"Copying to '{cp_file}'")
        cp_file.write_text(md_file.read_text())


def write_bookmarks_markdown_by_date(
    md_file: Path, n_hosts: int, bmks: list[Bookmark], cp_dir: Path
):
    print(f"Writing '{md_file}'")

    #  Re-sort bookmarks list. Ascending when_added for Markdown output.
    bmks.sort(key=lambda item: item.host_name.lower())
    bmks.sort(key=lambda item: item.url)
    bmks.sort(key=lambda item: item.when_added)

    with md_file.open("w") as f:
        f.write("# Bookmarks by Date Added\n\n")

        if n_hosts > 1:
            f.write("(Combined bookmarks from multiple hosts.)\n\n")
        elif bmks:
            f.write(f"On host **{bmks[0].host_name}** as of **{bmks[0].asof_dt}**.\n\n")

        host_str = ""

        for bmk in bmks:
            if n_hosts > 1:
                host_str = f"Host: `{bmk.host_name}`\n"

            title = limited(ascii(bmk.title)).strip("'")

            f.write(
                f"[{htm_txt(title)}]({htm_url(bmk.url)})\n"
                f"Added: `{bmk.when_added}`\n"
                f"Folder: `{htm_txt(bmk.parent_path)}`\n{host_str}\n"
            )

        f.write(
            "---\n\nCreated {0} by {1}".format(
                run_dt.strftime("%Y-%m-%d %H:%M"), app_title
            )
        )
    if cp_dir:
        cp_file = cp_dir / md_file.name
        print(f"Copying to '{cp_file}'")
        cp_file.write_text(md_file.read_text())


def get_parent_path(con, bookmark_parent_id):
    cur = con.cursor()
    max_depth = 99
    depth = 0
    parent_id = bookmark_parent_id
    parent_path = "/"
    while parent_id > 0:
        #  It appears that the root always has id=0. If that is not the case
        #  this max-depth check (99 seems like a good arbitrary value) will
        #  prevent an infinate loop.
        depth += 1
        if depth > max_depth:
            print("ERROR: parent_path max depth exceeded.")
            return f"/(ERROR){parent_path}"

        qry = (  # noqa: S608
            "SELECT parent, title FROM moz_bookmarks WHERE id = {0}"
        ).format(parent_id)

        cur.execute(qry)
        rows = cur.fetchall()
        assert len(rows) == 1  # noqa: S101

        parent_id = int(rows[0][0])
        if parent_id > 0:
            title = str(rows[0][1])
            parent_path = f"/{title}{parent_path}"

    return parent_path


def from_moz_date(moz_date) -> str:
    """
    The date values in the Mozilla sqlite database are in microseconds
    since the Unix epoch. This function converts the moz_date value to
    seconds, then to the equivalent datetime value.
    The date time value is returned as a formatted string.
    """
    dt_secs = moz_date / 1000000.0
    dt = datetime.fromtimestamp(dt_secs)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_bookmarks(con: sqlite3.Connection, host_name: str, asof: str) -> list[Bookmark]:
    """
    Queries the connected places.sqlite database and creates a
    list of bookmarks as Bookmark (namedtuple) items.
    The list is sorted by parent path and title.
    """
    bookmarks = []

    qry = dedent(
        """
        SELECT
            b.title,
            p.url,
            b.parent,
            b.dateAdded
        FROM
            moz_bookmarks b
        JOIN moz_places p
        ON p.id = b.fk
        """
    )

    cur = con.cursor()

    try:
        cur.execute(qry)
    except Exception as ex:
        if str(ex) == "database is locked":
            cur.close()
            con.close()
            sys.stderr.write(
                "\nERROR: Database is locked. Please close Firefox and try again.\n"
            )
            sys.exit(1)
        else:
            raise ex

    rows = cur.fetchall()

    for row in rows:
        url = str(row[1])

        if not url.startswith("http"):
            print(f"SKIP NON-HTTP URL: '{url}'")
            continue

        title = str(row[0])
        parent_id = int(row[2])

        if title is None:
            title = f"({url})"

        when_added = from_moz_date(row[3])

        bookmarks.append(
            Bookmark(
                title,
                url,
                get_parent_path(con, parent_id),
                when_added,
                host_name,
                asof,
            )
        )

    con.rollback()  # Should be no changes, but just in case...
    cur.close()
    return bookmarks


def exec_sql(cur: sqlite3.Cursor, stmt: str, data=None):
    try:
        if data:
            cur.execute(stmt, data)
        else:
            cur.execute(stmt)
    except Exception as e:
        print("\n{}\n".format(stmt))
        raise e


def get_bookmarks_from_db(
    con: sqlite3.Connection,
) -> tuple[int, list[Bookmark]]:
    # bookmarks = []
    cur = con.cursor()

    exec_sql(cur, "SELECT count(id) FROM hosts;")
    row = cur.fetchone()
    if row:
        n_hosts = int(row[0])
    else:
        assert 0, "Should be at least one host."  # noqa: S101
        n_hosts = 1

    qry = dedent(
        """
        SELECT title, url, parent_path, when_added,
            host_name, created
        FROM view_bookmarks
        ORDER BY parent_path, title
        """
    )

    exec_sql(cur, qry)

    bookmarks = [
        Bookmark(row[0], row[1], row[2], row[3], row[4], row[5])
        for row in cur.fetchall()
    ]

    cur.close()
    return (n_hosts, bookmarks)


def db_object_exists(con: sqlite3.Connection, obj_type: str, obj_name: str) -> bool:
    cur = con.cursor()
    qry = "SELECT name FROM sqlite_master WHERE type = ? AND name = ?;"
    exec_sql(
        cur,
        qry,
        (
            obj_type,
            obj_name,
        ),
    )
    row = cur.fetchone()
    cur.close()
    return bool(row)


def create_db_objects(con: sqlite3.Connection):
    cur = con.cursor()

    # Enable foreign key support (https://sqlite.org/foreignkeys.html#fk_enable).
    exec_sql(cur, "PRAGMA foreign_keys = ON;")

    if db_object_exists(con, "table", "hosts"):
        print("Table 'hosts' exists.")
    else:
        print("Creating table 'hosts'.")
        stmt = dedent(
            """
            CREATE TABLE hosts (
                id INTEGER PRIMARY KEY,
                host_name TEXT UNIQUE,
                source TEXT,
                created TEXT,
                app_name TEXT,
                app_version TEXT
            )
            """
        )
        exec_sql(cur, stmt)

    if db_object_exists(con, "table", "bookmarks"):
        print("Table 'bookmarks' exists.")
    else:
        print("Creating table 'bookmarks'.")
        stmt = dedent(
            """
            CREATE TABLE bookmarks (
                id INTEGER PRIMARY KEY,
                host_id INTEGER REFERENCES hosts(id) ON DELETE CASCADE,
                title TEXT,
                url TEXT,
                parent_path TEXT,
                when_added TEXT
            )
            """
        )
        exec_sql(cur, stmt)

    if db_object_exists(con, "view", "view_bookmarks"):
        print("View 'view_bookmarks' exists.")
    else:
        print("Creating view 'view_bookmarks'.")
        stmt = dedent(
            """
            CREATE VIEW view_bookmarks AS
                SELECT
                    b.id,
                    b.title,
                    b.url,
                    b.parent_path,
                    b.when_added,
                    b.host_id,
                    h.host_name,
                    h.created,
                    h.source
                FROM bookmarks b
                JOIN hosts h
                ON h.id = b.host_id;
            """
        )
        exec_sql(cur, stmt)

    con.commit()
    cur.close()


def insert_bookmarks(
    con: sqlite3.Connection, opts: AppOptions, bookmarks: list[Bookmark]
) -> bool:
    cur = con.cursor()

    assert opts.host_name  # noqa: S101

    qry = "SELECT host_name FROM hosts WHERE host_name = ?;"
    exec_sql(cur, qry, (opts.host_name,))
    row = cur.fetchone()
    if row:
        if opts.do_update:
            print(f"\nUpdating data for host '{opts.host_name}'.")
            exec_sql(cur, f"DELETE FROM hosts WHERE host_name = '{opts.host_name}';")  # noqa: S608
            con.commit()
        else:
            print(f"\nData for host '{opts.host_name}' is already in the database.")
            print("Duplicate data from same host is not allowed.\n")
            return False

    stmt = dedent(
        """
        INSERT INTO hosts (host_name, source, created, app_name, app_version)
        VALUES (?, ?, ?, ?, ?);
        """
    )
    data = (
        opts.host_name,
        str(opts.places_file),
        run_dt.strftime("%Y-%m-%d %H:%M:%S"),
        app_name,
        __version__,
    )
    exec_sql(cur, stmt, data)
    host_id = cur.lastrowid
    con.commit()

    for bmk in bookmarks:
        stmt = dedent(
            """
            INSERT INTO bookmarks (
                host_id, title, url, parent_path, when_added
            )
            VALUES (?, ?, ?, ?, ?);
            """
        )
        data = (host_id, bmk.title, bmk.url, bmk.parent_path, bmk.when_added)
        exec_sql(cur, stmt, data)

    con.commit()
    cur.close()
    return True


def get_asof_date(use_mtime: bool, places_file: Path) -> datetime:
    if use_mtime and places_file:
        return datetime.fromtimestamp(places_file.stat().st_mtime)
    return run_dt


def remove_previous_files(from_path: Path, base_name: str) -> None:
    for f in from_path.glob(f"{base_name}*"):
        print(f"Removing '{f}'")
        f.unlink()


def main(arglist=None):
    print(f"\n{app_title}\n")

    opts = get_opts(arglist)

    ok = True

    if opts.in_db:
        print(f"Reading {opts.in_db}")
        con = sqlite3.connect(str(opts.in_db))
        n_hosts, bookmarks = get_bookmarks_from_db(con)

        write_bookmarks_html(opts.output_file, bookmarks, opts.cp_dir)

        if opts.md_file:
            write_bookmarks_markdown(opts.md_file, bookmarks, opts.cp_dir)

        if opts.bydate_file:
            write_bookmarks_by_date_html(
                opts.bydate_file, n_hosts, bookmarks, opts.cp_dir
            )

        if opts.md_bydate:
            write_bookmarks_markdown_by_date(str(opts.md_bydate), n_hosts, bookmarks)
    else:
        print(f"Reading {opts.places_file}")
        con = sqlite3.connect(str(opts.places_file), timeout=1.0)
        asof = get_asof_date(opts.use_mtime, opts.places_file).strftime(
            "%Y-%m-%d %H:%M"
        )
        bookmarks = get_bookmarks(con, opts.host_name, asof)
        con.close()
        print("")

        if opts.out_db:
            print(f"Writing database '{opts.out_db}'")

            db = sqlite3.connect(str(opts.out_db))
            create_db_objects(db)

            ok = insert_bookmarks(db, opts, bookmarks)
            db.close()
        else:
            if opts.rm_prev:
                remove_previous_files(opts.output_file.parent, opts.base_name)
                remove_previous_files(opts.cp_dir, opts.base_name)

            write_bookmarks_html(opts.output_file, bookmarks, opts.cp_dir)

            if opts.md_file:
                write_bookmarks_markdown(opts.md_file, bookmarks, opts.cp_dir)

            if opts.bydate_file:
                write_bookmarks_by_date_html(
                    opts.bydate_file, 1, bookmarks, opts.cp_dir
                )

            if opts.md_bydate:
                write_bookmarks_markdown_by_date(
                    opts.md_bydate, 1, bookmarks, opts.cp_dir
                )

    if ok:
        print("\nDone.\n")
        return 0
    return 1


if __name__ == "__main__":
    main()
