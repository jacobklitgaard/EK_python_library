"""Sender bøgerne fra bog-API'et op som en gist på GitHub.

Kræver en .env-fil med:  GITHUB_TOKEN=github_pat_...
Kør med:                 uv run gist_client.py
(bog-serveren skal køre, fx:  uv run app.py)
"""

import json
import os

import httpx
from dotenv import load_dotenv

from client import list_books

load_dotenv()  # læser .env og lægger værdierne i os.environ

GITHUB_API = "https://api.github.com"
TIMEOUT = 10.0


def github_headers() -> dict[str, str]:
    # os.environ[...] kaster KeyError, hvis token mangler. Det vil vi gerne vide med det samme.
    token = os.environ["GITHUB_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def create_gist(filename: str, content: str, description: str = "", public: bool = False) -> dict:
    payload = {
        "description": description,
        "public": public,
        "files": {filename: {"content": content}},
    }
    r = httpx.post(f"{GITHUB_API}/gists", headers=github_headers(), json=payload, timeout=TIMEOUT)
    r.raise_for_status()  # forventet svar: 201 Created
    return r.json()


def get_gist(gist_id: str) -> dict:
    r = httpx.get(f"{GITHUB_API}/gists/{gist_id}", headers=github_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def delete_gist(gist_id: str) -> None:
    r = httpx.delete(f"{GITHUB_API}/gists/{gist_id}", headers=github_headers(), timeout=TIMEOUT)
    r.raise_for_status()  # forventet svar: 204 No Content, ingen body


def github_error_message(e: httpx.HTTPStatusError) -> str:
    try:
        return e.response.json()["message"]
    except (ValueError, KeyError):
        return e.response.text[:300] or "(tom body)"


def main() -> None:
    try:
        books = list_books()  # 1. hent bøgerne fra dit eget API
        print(f"Hentede {len(books)} bøger fra bog-API'et")

        # 2. send dem til GitHub
        gist = create_gist(
            "books.json",
            json.dumps(books, indent=2, ensure_ascii=False),
            description="Bøger fra mit bog-API",
        )
        print("Gist oprettet:", gist["html_url"])

        # 3. hent den igen, for at bevise at den ligger hos GitHub
        fetched = get_gist(gist["id"])
        print("Filer i gisten:", list(fetched["files"]))

        # 4. ryd op, så du ikke efterlader gists
        #delete_gist(gist["id"])
        #print("Gist slettet igen")
    except KeyError as e:
        if e.args and e.args[0] == "GITHUB_TOKEN":
            print("GITHUB_TOKEN mangler. Opret en .env-fil med GITHUB_TOKEN=...")
        else:
            raise
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        print(f"Serveren svarede {status}: {github_error_message(e)}")
        if status in (401, 403):
            print("Tjek at token'en er gyldig og har Gists: Read and write.")
    except httpx.ConnectError:
        print("Kunne ikke forbinde. Kører bog-serveren, og har du internet?")
    except httpx.TimeoutException:
        print("Serveren svarede ikke i tide.")


if __name__ == "__main__":
    main()