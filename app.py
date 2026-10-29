"""Bookshelf API for the student association.

Run with:  uv run --with flask python app.py
Docs:      GET /swagger.json (open it in https://editor.swagger.io/)
"""

import json
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

app = Flask(__name__)

import os

from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["LIBRARY_API_KEY"]

@app.before_request
def require_api_key():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("X-API-Key") != API_KEY:
        return error("Invalid or missing API key", 401)

# Books are saved to a JSON file so they survive a server restart.
# A plain Python list would be empty again every time the server starts.
DATA_FILE = Path(__file__).parent / "books.json"
SWAGGER_FILE = Path(__file__).parent / "swagger.json"


def load_books() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_books(books: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(books, indent=2, ensure_ascii=False), encoding="utf-8")


def find_book(books: list[dict], book_id: int) -> dict | None:
    return next((b for b in books if b["id"] == book_id), None)


def error(message: str, status: int):
    """All errors share the same shape, so the app team only has to handle one format."""
    return jsonify({"error": message}), status


@app.get("/books")
def list_books():
    books = load_books()
    # Optional filter: /books?available=true shows only books on the shelf
    available = request.args.get("available")
    if available is not None:
        want_available = available.lower() == "true"
        books = [b for b in books if (b["borrower"] is None) == want_available]
    return jsonify(books), 200


@app.get("/books/<int:book_id>")
def get_book(book_id: int):
    book = find_book(load_books(), book_id)
    if book is None:
        return error(f"Book {book_id} not found", 404)
    return jsonify(book), 200


@app.post("/books")
def add_book():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be JSON", 400)

    title = str(data.get("title", "")).strip()
    if not title:
        return error("'title' is required", 400)

    books = load_books()
    # Never reuse an id, even after a book has been deleted
    next_id = max((b["id"] for b in books), default=0) + 1
    book = {
        "id": next_id,
        "title": title,
        "author": str(data.get("author", "")).strip() or None,
        "borrower": None,
    }
    books.append(book)
    save_books(books)
    # 201 Created + Location header pointing at the new resource
    return jsonify(book), 201, {"Location": f"/books/{next_id}"}


@app.post("/books/<int:book_id>/loan")
def loan_book(book_id: int):
    data = request.get_json(silent=True) or {}
    borrower = str(data.get("borrower", "")).strip()
    if not borrower:
        return error("'borrower' is required", 400)

    books = load_books()
    book = find_book(books, book_id)
    if book is None:
        return error(f"Book {book_id} not found", 404)
    if book["borrower"] is not None:
        # 409 Conflict: the request is valid, but clashes with the book's current state
        return error(f"Book {book_id} is already loaned to {book['borrower']}", 409)

    book["borrower"] = borrower
    save_books(books)
    return jsonify(book), 200


@app.post("/books/<int:book_id>/return")
def return_book(book_id: int):
    books = load_books()
    book = find_book(books, book_id)
    if book is None:
        return error(f"Book {book_id} not found", 404)
    if book["borrower"] is None:
        return error(f"Book {book_id} is not loaned out", 409)

    book["borrower"] = None
    save_books(books)
    return jsonify(book), 200


@app.delete("/books/<int:book_id>")
def delete_book(book_id: int):
    books = load_books()
    book = find_book(books, book_id)
    if book is None:
        return error(f"Book {book_id} not found", 404)

    books.remove(book)
    save_books(books)
    # 204 No Content: it worked, and there is nothing to send back
    return "", 204

# stream books one by one, with a 1 second delay between each book. The client can read the stream as it arrives, instead of waiting for all books to be sent at once. This is useful for long-running requests or when the client wants to display results as they arrive. The response is in the Server-Sent Events (SSE) format, which is a simple text-based protocol for sending events from the server to the client over HTTP. Each event is sent as a block of text starting with "data: " and ending with two newlines. The client can listen for these events and process them as they arrive. The last event is a special "[DONE]" message indicating that there are no more books to send.

@app.get("/books/stream")
def stream_books():
    def generate():
        for book in load_books():
            yield f"data: {json.dumps(book, ensure_ascii=False)}\n\n"
            time.sleep(1)  # kun for at du kan se effekten
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.get("/swagger.json")
def swagger():
    return send_file(SWAGGER_FILE, mimetype="application/json")


# Unknown URLs and wrong methods return JSON instead of Flask's default HTML pages
@app.errorhandler(404)
def not_found(_):
    return error("Endpoint not found", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return error("Method not allowed on this endpoint", 405)


if __name__ == "__main__":
    app.run(debug=True, port=5001)