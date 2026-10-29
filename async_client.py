"""Asynkron version: henter flere bøger samtidigt med AsyncClient og asyncio.gather.

Kør med:  uv run async_client.py
(bog-serveren skal køre, fx:  uv run app.py)
"""

import asyncio
import time

import httpx

BASE = "http://127.0.0.1:5001"
TIMEOUT = 5.0


async def get_book(client: httpx.AsyncClient, book_id: int) -> dict:
    r = await client.get(f"/books/{book_id}")
    r.raise_for_status()
    return r.json()


async def fetch_all_async(ids: list[int]) -> list[dict]:
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        # gather starter alle kald på samme tid og venter, til de alle er færdige
        return await asyncio.gather(*(get_book(client, i) for i in ids))


def fetch_all_sync(ids: list[int]) -> list[dict]:
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        results = []
        for i in ids:  # ét kald ad gangen
            r = client.get(f"/books/{i}")
            r.raise_for_status()
            results.append(r.json())
        return results


def existing_ids() -> list[int]:
    r = httpx.get(f"{BASE}/books", timeout=TIMEOUT)
    r.raise_for_status()
    return [b["id"] for b in r.json()]


async def main() -> None:
    try:
        ids = existing_ids()
        print(f"Henter {len(ids)} bøger: {ids}")

        start = time.perf_counter()
        fetch_all_sync(ids)
        print(f"Synkront:   {time.perf_counter() - start:.4f} sekunder")

        start = time.perf_counter()
        books = await fetch_all_async(ids)
        print(f"Asynkront:  {time.perf_counter() - start:.4f} sekunder")

        for book in books:
            print(book["id"], book["title"])

        # Fejl i et af kaldene: return_exceptions=True lader de andre kald fuldføre
        async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
            results = await asyncio.gather(
                get_book(client, ids[0]),
                get_book(client, 99999),  # findes ikke, giver 404
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, httpx.HTTPStatusError):
                print(f"Et kald fejlede med {result.response.status_code}")
            elif isinstance(result, BaseException):
                print("Et kald fejlede:", result)
            else:
                print("OK:", result["title"])
    except httpx.ConnectError:
        print("Kunne ikke forbinde. Kører serveren?")
    except httpx.TimeoutException:
        print("Serveren svarede ikke i tide.")
    except httpx.HTTPStatusError as e:
        print(f"Serveren svarede {e.response.status_code}")


if __name__ == "__main__":
    asyncio.run(main())