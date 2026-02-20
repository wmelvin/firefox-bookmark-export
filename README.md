# firefox-bookmark-export

**fbx.py** is a command-line utility that reads the Firefox *places.sqlite* database and writes a HTML file listing the saved bookmarks.

This program borrows from the earlier [firefox-places](https://github.com/wmelvin/firefox-places) utility.

If no command-line arguments are given, the common location for Firefox profiles is searched and the most recently modified `places.sqlite` file is used. The default output file is named `Firefox-bookmarks-*hostname*-*date_time*.html` and is written to the user's `Desktop` folder.

There are additional options for writing to a SQLite database file instead of creating HTML files. This affords gathering bookmarks from multiple hosts. The database file can then be used as the source for generating the HTML output.


```
usage: fbx [-h] [--profile PROFILE] [--places-file PLACES_FILE] [--asof-mtime]
           [--output-name OUTPUT_FILE] [--output-folder OUTPUT_FOLDER]
           [--by-date] [--md] [--output-sqlite OUTPUT_DB]
           [--host-name HOST_NAME] [--update] [--from-sqlite SOURCE_DB]
           [--cp-dir CP_DIR] [--rm-prev] [--csv]

Exports Firefox bookmarks to a single HTML file.

options:
  -h, --help            show this help message and exit
  --profile PROFILE     Path to the Firefox profile folder.
  --places-file PLACES_FILE
                        Path to a specific version of the 'places.sqlite'
                        file. Overrides the '--profile' options.
  --asof-mtime          Use the modified time of the 'places.sqlite' file for
                        the 'as of' date-time listed in the output files.
  --output-name OUTPUT_FILE
                        Name of the output HTML file.
  --output-folder OUTPUT_FOLDER
                        Name of the folder in which to create the output HTML
                        file.
  --by-date             Also produce an output file listing bookmarks by date-
                        added (most recent first). The name of the output file
                        will be the same as the main output file with
                        '-bydate' added to the file name.
  --md                  Also produce a Markdown file listing the bookmarks The
                        name of the output file will be the same as the HTML
                        output file with a '.md' suffix. If the --by-date
                        switch is used, a separate Markdown file by date
                        (oldest first) is produced.
  --output-sqlite OUTPUT_DB
                        Name of the SQLite database file to produce instead of
                        HTML files. This overrides the --output-name and --by-
                        date options, but still uses the --output-folder
                        option. If the database file already exists, new data
                        is appended (but only if from a different host).
  --host-name HOST_NAME
                        Use a specified host name, instead of the current
                        machine's host name. This is useful when reading data
                        from a copy of a 'places.sqlite' file taken from
                        another machine.
  --update              Update SQLite output database with the data from the
                        specified 'places.sqlite' file. This is required if
                        you want to insert (replace) data from a host that is
                        already in the database.
  --from-sqlite SOURCE_DB
                        Name of a SQLite database, previously created by fbx,
                        from which to get the list of bookmarks for producing
                        the HTML output files. This must be the full path to
                        the file (unless it is in the current directory)
  --cp-dir CP_DIR       Write a second copy the output files to the specified
                        directory. Only applies to HTML and Markdown files.
  --rm-prev             Remove previous output files in the output folder.
                        Only applies to HTML and Markdown files.
  --csv                 Also produce a CSV file listing the bookmarks sorted
                        by date added (most recent first). The name of the
                        output file will be the same as the main output file
                        with a '.csv' suffix.
```