## Protravel

### Path traversal

Directory traversal or path traversal makes it possible to access any file on the webserver. For example, consider the following URL vulnerable:

    http://example.com/getfile.php?filename=export2018.csv

Then the following URL may return /etc/passwd from the server:

    http://example.com/getfile.php?filename=../../../../../../etc/passwd

We use `../` to go a directory up and download a file outside of the directory that getfile.php normally reads the exports from.

With path traversal it is generally possible to download any file by name, but not possible to get any directory listings. This means that we have to guess filenames if we want to download them. That is the task that protravel performs.

### Finding filenames

Protravel contains a list of interesting files to download. Some of these files, especially log files, contain paths of other files. Protravel will download these, and in this way try to spider the filesystem.

It can also parse /etc/passwd to read the home directories from it, and search for .ssh and .bashrc files in home directories.

### Usage

Call protravel with a URL as argument. The path to download will be appended to the URL.

    protravel.py http://example.com/getfile.php?filename=../../../../..

All found files are written to a directory, `out` by default.
