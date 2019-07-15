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

session = None


def get_page(url: str, fresh: bool = False, cache: pathlib.Path = pathlib.Path('cache/')) -> str:
    p = cache / (slugify.slugify(url) + '.html')
    print(f"{DARK}{url} → {p}", end=" ")
    if p.is_file() and not fresh:
        print(f"{DARK}– from cache")
        return p.read_text('utf-8')
    print(f"{DARK}– fetch")

    global session
    if session is None:
        session = requests.Session()
        login_url = url.replace("ranking", "login")
        print(f"{DARK}Logging in – {login_url}")
        session.get(login_url)

        secret_file = pathlib.Path("secret.yaml")
        assert secret_file.is_file(), "Please create file secret.yaml with username and password, see --help."
        secret = yaml.safe_load(secret_file.read_text("utf-8"))
        login_response = session.post(login_url, data={
            "csrfmiddlewaretoken": session.cookies["csrftoken"],
            "username": secret.get("username"),
            "password": secret.get("password")
        }, headers={
            "Referer": login_url
        })
        assert not "error" in login_response.text.lower(), "Login probably failed."

    page = session.get(url).text
    os.makedirs(str(cache), exist_ok=True)
    p.write_text(page, 'utf-8')
    return page


def parse_ranking(page: str) -> Iterator[Tuple[str, int]]:
    soup = bs4.BeautifulSoup(page, 'html.parser')

    ranking, = [o for o in soup.find_all('table') if 'table-ranking' in o['class']]
    for row in ranking.find_all('tr'):
        if row.find_all('th'):
            continue
        name, = [str(o.get_text()).strip() for o in row.find_all('td') if 'user-cell' in o['class']]
        _, points, *_ = [int(o.get_text()) for o in row.find_all('td') if
                         'text-right' in o['class'] and o.get_text().strip()]
        yield name, points


if __name__ == '__main__':
    default_urls = ["http://10.0.0.1/c/grupaa/ranking/",
                    "http://10.0.0.1/c/grupa-b/ranking/",
                    "http://10.0.0.1/c/grupa-c/ranking/"]
    default_multipliers = [10, 3, 1]

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="As of recently, a file secrets.yaml with fields 'username' and 'password' "
                                            "is required to log in. Example:\n"
                                            "    username: ahitler\n"
                                            "    password: correct horse battery staple\n"
                                            "\n"
                                            "Please report any issues at GitHub: "
                                            "<https://github.com/Aleshkev/sio2-watcher>")
    parser.add_argument('--fresh', '-f', help="Don't use cached page", action='store_true')
    parser.add_argument('--urls', '-l', metavar='L', type=str, nargs='+', help="URLs of the rankings",
                        default=default_urls)
    parser.add_argument('--multipliers', '-m', metavar='M', type=float, nargs='+', help="Multipliers of the rankings",
                        default=default_multipliers)
    args = parser.parse_args()
    args.fresh: bool
    args.urls: Tuple[str]
    args.multipliers: Tuple[float]

    assert len(args.urls) == len(args.multipliers)
    n = len(args.urls)

    colorama.init(autoreset=True)

    scores: Dict[str, Tuple[float, Tuple[float, ...]]] = collections.defaultdict(lambda: (0, (0,) * n))
    for i, (url, multiplier) in enumerate(zip(args.urls, args.multipliers)):
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
