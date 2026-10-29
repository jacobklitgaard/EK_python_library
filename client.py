import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv("client.env")

BASE = "http://127.0.0.1:5001"
TIMEOUT = 5.0

client = httpx.Client(
    base_url=BASE,
    headers={"X-API-Key": os.environ["LIBRARY_API_KEY"]},
    timeout=TIMEOUT,
)


def list_books(available: bool | None = None) -> list[dict]:
    params = {} if available is None else {"available": str(available).lower()}
    r = client.get("/books", params=params)
    r.raise_for_status()
    return r.json()


def get_book(book_id: int) -> dict:
    r = client.get(f"/books/{book_id}")
    r.raise_for_status()
    return r.json()


def add_book(title: str, author: str | None = None) -> dict:
    body = {"title": title}
    if author is not None:
        body["author"] = author
    r = client.post("/books", json=body)
    r.raise_for_status()
    return r.json()


def loan_book(book_id: int, borrower: str) -> dict:
    r = client.post(f"/books/{book_id}/loan", json={"borrower": borrower})
    r.raise_for_status()
    return r.json()


def return_book(book_id: int) -> dict:
    r = client.post(f"/books/{book_id}/return")
    r.raise_for_status()
    return r.json()


def delete_book(book_id: int) -> None:
    r = client.delete(f"/books/{book_id}")
    r.raise_for_status()

# streaming endpoint: /books/stream

def stream_books() -> None:
    with httpx.stream("GET", "http://127.0.0.1:5001/books/stream", timeout=10.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line.removeprefix("data: ")
            if payload == "[DONE]":
                break
            print(json.loads(payload))


# --- Testprogram: her kaldes funktionerne ---

def main() -> None:
    try:
        books = list_books()  # henter alle bøger
        print("Alle bibliotekets bøger:", books)
        
        book = add_book("Dune", "Frank Herbert") # Tilføjer bog
        print("Oprettet:", book)

        print("Udlånt:", loan_book(book["id"], "Jacob")) # Udlåner bog
        print("På hylden:", list_books(available=True)) # Tilgængelige bøger

        returned = return_book(book["id"]) # Returnerer bog
        print("Returneret:", returned) 

        delete_book(book["id"])
        print("Slettet bog", book["id"])

        try:
            get_book(book["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print("Bekræftet: bogen findes ikke længere (404)")
            else:
                raise  # en anden fejl end 404 er uventet, så den sendes videre

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            print("Bogen findes ikke (404)")
        elif status == 400:
            print("Ugyldig forespørgsel (400):", e.response.text[:300])
        elif status == 401:
            print("Mangler eller forkert API-nøgle (401)")
        else:
            print(f"Serveren svarede {status}:", e.response.text[:300] or "(tom)")
    except httpx.ConnectError:
        print("Kunne ikke forbinde. Kører serveren?")
    except httpx.TimeoutException:
        print("Serveren svarede ikke i tide.")


if __name__ == "__main__":
    main()