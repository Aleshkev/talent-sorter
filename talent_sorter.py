import argparse
import collections
import os
import pathlib
from typing import *

import bs4
import requests
import colorama
import slugify
import yaml

DARK = colorama.Style.BRIGHT + colorama.Fore.BLACK
GREY = colorama.Style.DIM + colorama.Fore.WHITE
WHITE = colorama.Style.BRIGHT + colorama.Fore.WHITE


def bs(page: str):
    return bs4.BeautifulSoup(page, "html.parser")


session = None


def get_page(url: str, fresh: bool = False, cache: pathlib.Path = pathlib.Path("cache/")) -> str:
    p = cache / (slugify.slugify(url) + ".html")
    print(f"{DARK}{url} → {p}", end=" ")
    if p.is_file() and not fresh:
        print(f"{DARK}– from cache")
        return p.read_text("utf-8")
    print(f"{DARK}– fetch")

    global session
    if session is None:
        session = requests.Session()
        login_url = url.replace("ranking", "login")
        print(f"{DARK}Logging in – {login_url}")
        session.get(login_url)

        secret_file = pathlib.Path("secret.yaml")
        assert secret_file.is_file(), "Please create file secret.yaml with, see --help."
        secret = yaml.safe_load(secret_file.read_text("utf-8"))
        username = secret.get("username").strip()
        password = secret.get("password").strip()
        login_response = session.post(login_url, data={
            "csrfmiddlewaretoken": session.cookies["csrftoken"],
            "username": username,
            "password": password
        }, headers={
            "Referer": login_url
        })
        assert bs(login_response.text).find(id="navbar-username").text.strip() == username, "Login probably failed."

    page = session.get(url).text
    os.makedirs(str(cache), exist_ok=True)
    p.write_text(bs(page).prettify(), "utf-8")
    return page


def parse_ranking(page: str) -> Iterator[Tuple[str, int]]:
    soup = bs(page)

    ranking, = [o for o in soup.find_all("table") if "table-ranking" in o["class"]]
    for row in ranking.find_all("tr"):
        if row.find_all("th"):
            continue
        name, = [str(o.get_text()).strip() for o in row.find_all("td", class_="user-cell")]
        _, points, *_ = [int(o.get_text()) for o in row.find_all("td", class_="text-right") if o.get_text().strip()]
        yield name, points


manual = """
Since viewing rankings now requires logging in, a file with username and 
password is needed. Please create a file secret.yaml with fields 'username'
and 'password':

    username: rszubartowski
    password: Pr0gr4nn0vv4n13M3nt41n3
    
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=manual)
    parser.add_argument("--fresh", "-f", help="don't use cached pages", action="store_true")
    parser.add_argument("--default", "-d", help="add all default sources (from default_sources.yaml)",
                        action="store_true")
    parser.add_argument("--url", "-l", help="add one source: L – URL, M – multiplier", action="append", nargs=2,
                        metavar=("L", "M"), dest="sources", default=[])
    args = parser.parse_args()
    args.fresh: bool
    args.default: bool
    args.sources: List[Tuple[str, str]]

    sources = []
    if args.default:
        l = pathlib.Path("default_sources.txt").read_text().replace("\n", " ").split()
        for url, multiplier in zip(l[0::2], l[1::2]):
            sources.append((url, float(multiplier)))
    for (url, multiplier) in args.sources:
        sources.append((url, float(multiplier)))
    n = len(sources)

    sources.sort(key=lambda v: v[1], reverse=True)

    sources = [(url, int(multiplier) if int(multiplier) == multiplier else multiplier) for (url, multiplier) in sources]
    assert len(sources) > 0, "No sources to get data from."

    colorama.init(autoreset=True)

    for (url, multiplier) in sources:
        print(f"{DARK}{url} {GREY}× {multiplier}")

    scores: Dict[str, Tuple[float, Tuple[float, ...]]] = collections.defaultdict(lambda: (0, (0,) * n))
    for i, (url, multiplier) in enumerate(sources):
        for person, score in parse_ranking(get_page(url, args.fresh)):
            total, detailed = scores[person]
            scores[person] = (total + score * multiplier, detailed[:i] + (score,) + detailed[i + 1:])

    all_integer = all(int(x[0]) == x[0] for x in scores.values())
    max_surname = max(len(x) for x in scores.keys())

    print()
    for i, person in enumerate(sorted(scores.keys(), key=lambda x: scores[x][0], reverse=True)):
        total, detailed = scores[person]

        print(f"{GREY} {i + 1:>2}. {WHITE}{person:>{max_surname}} "
              f"{GREY}{total if all_integer else round(total, 2):<7} "
              f"{DARK}" + " ".join(f"{d:<4}" for d in detailed))
