"""A small, local-first library record manager."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DATA_VERSION = 1
CRITICAL_AVAILABLE_COPIES = 0
DEFAULT_DATA_FILE = Path(__file__).with_name("library_data.json")
BOOK_FIELDS = ("id", "title", "author", "category", "total_copies", "available_copies")
MEMBER_FIELDS = ("id", "name", "email", "joined_on")
LOAN_FIELDS = ("id", "book_id", "member_id", "issue_date", "due_date", "return_date")


class StoreError(Exception):
    """Raised when persisted library data cannot safely be used."""


def _spreadsheet_safe(value: Any) -> Any:
    """Keep untrusted text from being evaluated as a spreadsheet formula."""
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def _demo_state() -> dict[str, Any]:
    titles = [
        ("The Hobbit", "J.R.R. Tolkien", "Fantasy"),
        ("Pride and Prejudice", "Jane Austen", "Fiction"),
        ("1984", "George Orwell", "Fiction"),
        ("To Kill a Mockingbird", "Harper Lee", "Fiction"),
        ("The Great Gatsby", "F. Scott Fitzgerald", "Fiction"),
        ("A Brief History of Time", "Stephen Hawking", "Science"),
        ("The Selfish Gene", "Richard Dawkins", "Science"),
        ("Cosmos", "Carl Sagan", "Science"),
        ("Clean Code", "Robert C. Martin", "Technology"),
        ("The Pragmatic Programmer", "David Thomas", "Technology"),
        ("Introduction to Algorithms", "Thomas H. Cormen", "Technology"),
        ("Python Crash Course", "Eric Matthes", "Technology"),
        ("The Design of Everyday Things", "Don Norman", "Design"),
        ("Sapiens", "Yuval Noah Harari", "History"),
        ("Guns, Germs, and Steel", "Jared Diamond", "History"),
        ("The Diary of a Young Girl", "Anne Frank", "History"),
        ("The Alchemist", "Paulo Coelho", "Fiction"),
        ("The Book Thief", "Markus Zusak", "Fiction"),
        ("Little Women", "Louisa May Alcott", "Fiction"),
        ("The Odyssey", "Homer", "Classics"),
        ("Meditations", "Marcus Aurelius", "Philosophy"),
        ("The Republic", "Plato", "Philosophy"),
        ("Thinking, Fast and Slow", "Daniel Kahneman", "Psychology"),
        ("Man's Search for Meaning", "Viktor E. Frankl", "Psychology"),
        ("The Art of War", "Sun Tzu", "Philosophy"),
        ("The Elements of Style", "William Strunk Jr.", "Writing"),
        ("On Writing", "Stephen King", "Writing"),
        ("The Body Keeps the Score", "Bessel van der Kolk", "Psychology"),
        ("Factfulness", "Hans Rosling", "Science"),
        ("The Little Prince", "Antoine de Saint-Exupery", "Classics"),
    ]
    books = [
        {
            "id": "B0001" if index == 0 else "B%04d" % (index + 1),
            "title": title,
            "author": author,
            "category": category,
            "total_copies": 4 if index % 3 == 0 else 2,
            "available_copies": (4 if index % 3 == 0 else 2) - (1 if index < 4 else 0),
        }
        for index, (title, author, category) in enumerate(titles)
    ]
    member_names = [
        ("Aarav Sharma", "aarav.sharma@example.edu"),
        ("Maya Patel", "maya.patel@example.edu"),
        ("Ethan Wilson", "ethan.wilson@example.edu"),
        ("Sofia Garcia", "sofia.garcia@example.edu"),
        ("Noah Kim", "noah.kim@example.edu"),
        ("Aisha Khan", "aisha.khan@example.edu"),
        ("Liam Chen", "liam.chen@example.edu"),
        ("Priya Nair", "priya.nair@example.edu"),
        ("Oliver Brown", "oliver.brown@example.edu"),
        ("Zara Ahmed", "zara.ahmed@example.edu"),
    ]
    today = date.today()
    members = [
        {
            "id": "M%04d" % (index + 1),
            "name": name,
            "email": email,
            "joined_on": (today - timedelta(days=30 * (index + 1))).isoformat(),
        }
        for index, (name, email) in enumerate(member_names)
    ]
    loans = []
    for index in range(5):
        issue = today - timedelta(days=(24, 8, 15, 20, 35)[index])
        due = issue + timedelta(days=14)
        returned = (today - timedelta(days=5)).isoformat() if index == 4 else None
        loans.append(
            {
                "id": "L%04d" % (index + 1),
                "book_id": "B%04d" % (index + 1),
                "member_id": "M%04d" % (index + 1),
                "issue_date": issue.isoformat(),
                "due_date": due.isoformat(),
                "return_date": returned,
            }
        )
    return {"version": DATA_VERSION, "books": books, "members": members, "loans": loans}


class LibraryStore:
    def __init__(self, path: Path = DEFAULT_DATA_FILE):
        self.path = path
        self.data: dict[str, Any] = {}

    def load(self) -> None:
        if not self.path.exists():
            self.data = _demo_state()
            self.save()
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            self._validate(loaded)
        except (OSError, json.JSONDecodeError, StoreError) as exc:
            raise StoreError(
                "Cannot load library data from %s: %s. The file was left unchanged."
                % (self.path, exc)
            ) from exc
        self.data = loaded

    @staticmethod
    def _validate(data: Any) -> None:
        if not isinstance(data, dict) or data.get("version") != DATA_VERSION:
            raise StoreError("unsupported or missing data version")
        for key in ("books", "members", "loans"):
            if not isinstance(data.get(key), list):
                raise StoreError("'%s' must be a list" % key)
        book_ids = set()
        member_ids = set()
        loan_ids = set()
        member_emails = set()
        for book in data["books"]:
            if not isinstance(book, dict) or not all(field in book for field in BOOK_FIELDS):
                raise StoreError("invalid book record")
            if not all(isinstance(book[field], str) and book[field].strip() for field in
                       ("id", "title", "author", "category")):
                raise StoreError("book text fields must be non-empty strings")
            if book["id"] in book_ids:
                raise StoreError("duplicate book ID")
            book_ids.add(book["id"])
            if (
                not isinstance(book["total_copies"], int)
                or not isinstance(book["available_copies"], int)
                or book["total_copies"] < 1
                or not 0 <= book["available_copies"] <= book["total_copies"]
            ):
                raise StoreError("invalid copy count for book %s" % book["id"])
        for member in data["members"]:
            if not isinstance(member, dict) or not all(field in member for field in MEMBER_FIELDS):
                raise StoreError("invalid member record")
            if not all(isinstance(member[field], str) and member[field].strip() for field in
                       ("id", "name", "email", "joined_on")):
                raise StoreError("member fields must be non-empty strings")
            if member["id"] in member_ids:
                raise StoreError("duplicate member ID")
            member_ids.add(member["id"])
            if member["email"].casefold() in member_emails:
                raise StoreError("duplicate member email")
            member_emails.add(member["email"].casefold())
            try:
                date.fromisoformat(member["joined_on"])
            except ValueError as exc:
                raise StoreError("member contains an invalid join date") from exc
        active_by_book: dict[str, int] = {}
        for loan in data["loans"]:
            if not isinstance(loan, dict) or not all(field in loan for field in LOAN_FIELDS):
                raise StoreError("invalid loan record")
            if not isinstance(loan["id"], str) or not loan["id"].strip():
                raise StoreError("loan ID must be a non-empty string")
            if loan["id"] in loan_ids:
                raise StoreError("duplicate loan ID")
            loan_ids.add(loan["id"])
            if not all(isinstance(loan[field], str) for field in
                       ("book_id", "member_id", "issue_date", "due_date")):
                raise StoreError("loan references and dates must be strings")
            if loan["book_id"] not in book_ids or loan["member_id"] not in member_ids:
                raise StoreError("loan references a missing book or member")
            if loan["return_date"] is not None and not isinstance(loan["return_date"], str):
                raise StoreError("return date must be a date string or null")
            try:
                issue = date.fromisoformat(loan["issue_date"])
                due = date.fromisoformat(loan["due_date"])
                returned = date.fromisoformat(loan["return_date"]) if loan["return_date"] else None
            except (TypeError, ValueError) as exc:
                raise StoreError("loan contains an invalid date") from exc
            if due < issue or (returned is not None and returned < issue):
                raise StoreError("loan dates are inconsistent")
            if returned is None:
                active_by_book[loan["book_id"]] = active_by_book.get(loan["book_id"], 0) + 1
        for book in data["books"]:
            if book["available_copies"] != book["total_copies"] - active_by_book.get(book["id"], 0):
                raise StoreError("available copies do not match active loans for book %s" % book["id"])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(self.path.parent), delete=False
            ) as temp_file:
                temp_path = temp_file.name
                json.dump(self.data, temp_file, indent=2, ensure_ascii=False)
                temp_file.write("\n")
            os.replace(temp_path, self.path)
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise StoreError("Cannot save library data to %s: %s" % (self.path, exc)) from exc


class Library:
    def __init__(self, store: LibraryStore):
        self.store = store
        self.data = store.data

    def _next_id(self, collection: str, prefix: str) -> str:
        numbers = [
            int(record["id"][1:])
            for record in self.data[collection]
            if re.fullmatch(r"%s\d+" % prefix, record.get("id", ""))
        ]
        return "%s%04d" % (prefix, max(numbers, default=0) + 1)

    def add_book(
        self, title: str, author: str, category: str, copies: int = 1
    ) -> dict[str, Any]:
        title, author, category = title.strip(), author.strip(), category.strip()
        if not title or not author or not category:
            raise ValueError("Title, author, and category are required.")
        if not isinstance(copies, int) or copies < 1 or copies > 1000:
            raise ValueError("Copies must be a whole number from 1 to 1000.")
        book = {
            "id": self._next_id("books", "B"),
            "title": title,
            "author": author,
            "category": category,
            "total_copies": copies,
            "available_copies": copies,
        }
        self.data["books"].append(book)
        self.store.save()
        return book

    def add_member(self, name: str, email: str) -> dict[str, Any]:
        name, email = name.strip(), email.strip().lower()
        if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a member name and a valid email address.")
        if any(member["email"].lower() == email for member in self.data["members"]):
            raise ValueError("A member with that email already exists.")
        member = {
            "id": self._next_id("members", "M"),
            "name": name,
            "email": email,
            "joined_on": date.today().isoformat(),
        }
        self.data["members"].append(member)
        self.store.save()
        return member

    def checkout(self, book_id: str, member_id: str, days: int = 14) -> dict[str, Any]:
        book = self._find(self.data["books"], book_id)
        self._find(self.data["members"], member_id)
        if not isinstance(days, int) or not 1 <= days <= 90:
            raise ValueError("Loan period must be from 1 to 90 days.")
        if book["available_copies"] < 1:
            raise ValueError("No copies of that book are currently available.")
        loan = {
            "id": self._next_id("loans", "L"),
            "book_id": book_id,
            "member_id": member_id,
            "issue_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=days)).isoformat(),
            "return_date": None,
        }
        book["available_copies"] -= 1
        self.data["loans"].append(loan)
        self.store.save()
        return loan

    def return_book(self, loan_id: str) -> dict[str, Any]:
        loan = self._find(self.data["loans"], loan_id)
        if loan["return_date"]:
            raise ValueError("That loan has already been returned.")
        book = self._find(self.data["books"], loan["book_id"])
        loan["return_date"] = date.today().isoformat()
        book["available_copies"] += 1
        self.store.save()
        return loan

    @staticmethod
    def _find(records: list[dict[str, Any]], record_id: str) -> dict[str, Any]:
        for record in records:
            if record["id"].casefold() == record_id.strip().casefold():
                return record
        raise ValueError("No record found with ID %s." % record_id)

    def search(self, collection: str, query: str = "", category: str = "") -> list[dict[str, Any]]:
        if collection not in ("books", "members", "loans"):
            raise ValueError("Unknown record type.")
        records = self.data[collection]
        query, category = query.casefold().strip(), category.casefold().strip()
        results = []
        for record in records:
            haystack = " ".join(str(value) for value in record.values()).casefold()
            if query and query not in haystack:
                continue
            if category and (
                collection != "books" or category not in record["category"].casefold()
            ):
                continue
            results.append(record)
        return results

    def summary(self) -> dict[str, Any]:
        today = date.today()
        active = [loan for loan in self.data["loans"] if not loan["return_date"]]
        overdue = [
            loan for loan in active if date.fromisoformat(loan["due_date"]) < today
        ]
        out_of_stock = [
            book
            for book in self.data["books"]
            if book["available_copies"] == CRITICAL_AVAILABLE_COPIES
        ]
        category_counts: dict[str, int] = {}
        for book in self.data["books"]:
            category_counts[book["category"]] = category_counts.get(book["category"], 0) + 1
        return {
            "books": len(self.data["books"]),
            "members": len(self.data["members"]),
            "loans_total": len(self.data["loans"]),
            "loans_active": len(active),
            "loans_overdue": len(overdue),
            "books_out_of_stock": len(out_of_stock),
            "copies_total": sum(book["total_copies"] for book in self.data["books"]),
            "copies_available": sum(book["available_copies"] for book in self.data["books"]),
            "average_copies_per_title": (
                sum(book["total_copies"] for book in self.data["books"])
                / len(self.data["books"])
                if self.data["books"]
                else 0
            ),
            "categories": category_counts,
        }

    def export(self, directory: Path) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        generated = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "# Library Summary",
            "",
            "Generated: %s" % generated,
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        metrics = (
            ("Book titles", "books"),
            ("Members", "members"),
            ("Loans (total)", "loans_total"),
            ("Loans (active)", "loans_active"),
            ("Overdue loans", "loans_overdue"),
            ("Out-of-stock titles", "books_out_of_stock"),
            ("Copies available", "copies_available"),
            ("Average copies per title", "average_copies_per_title"),
        )
        lines.extend("| %s | %s |" % (label, summary[key]) for label, key in metrics)
        lines.extend(["", "## Titles by category", ""])
        lines.extend("- %s: %s" % item for item in sorted(summary["categories"].items()))
        markdown = "\n".join(lines) + "\n"
        report_txt = markdown.replace("# Library Summary", "LIBRARY SUMMARY").replace(
            "|", " "
        )
        paths = [
            directory / "library_summary.md",
            directory / "library_summary.txt",
            directory / "books.csv",
        ]
        paths[0].write_text(markdown, encoding="utf-8")
        paths[1].write_text(report_txt, encoding="utf-8")
        with paths[2].open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=BOOK_FIELDS)
            writer.writeheader()
            writer.writerows(
                {
                    field: _spreadsheet_safe(book.get(field, ""))
                    for field in BOOK_FIELDS
                }
                for book in self.data["books"]
            )
        return paths


def prompt_text(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Please enter a value.")


def prompt_int(label: str, minimum: int, maximum: int, default: int | None = None) -> int:
    while True:
        raw = input("%s%s: " % (label, " [%d]" % default if default is not None else "")).strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if minimum <= value <= maximum:
            return value
        print("Enter a number from %d to %d." % (minimum, maximum))


def show_records(records: list[dict[str, Any]]) -> None:
    if not records:
        print("No matching records.")
        return
    for record in records:
        print(" | ".join("%s: %s" % (key, value if value is not None else "active")
                         for key, value in record.items()))


def run_app(store: LibraryStore) -> None:
    library = Library(store)
    print("\n=== CampusSolve Library Records ===")
    while True:
        print(
            "\n1. Add book  2. Add member  3. Check out book  4. Return book\n"
            "5. Search/list records  6. Summary  7. Export reports  0. Exit"
        )
        choice = input("Choose an option: ").strip()
        try:
            if choice == "1":
                book = library.add_book(
                    prompt_text("Title: "),
                    prompt_text("Author: "),
                    prompt_text("Category: "),
                    prompt_int("Copies", 1, 1000, 1),
                )
                print("Added %s: %s" % (book["id"], book["title"]))
            elif choice == "2":
                member = library.add_member(prompt_text("Name: "), prompt_text("Email: "))
                print("Added member %s: %s" % (member["id"], member["name"]))
            elif choice == "3":
                show_records(library.search("books"))
                loan = library.checkout(
                    prompt_text("Book ID: ").upper(),
                    prompt_text("Member ID: ").upper(),
                    prompt_int("Loan days", 1, 90, 14),
                )
                print("Checked out as %s; due %s." % (loan["id"], loan["due_date"]))
            elif choice == "4":
                active = [loan for loan in library.data["loans"] if not loan["return_date"]]
                show_records(active)
                loan = library.return_book(prompt_text("Loan ID: ").upper())
                print("Returned loan %s." % loan["id"])
            elif choice == "5":
                kind = input("Record type (books/members/loans): ").strip().lower()
                query = input("Keyword (blank for all): ").strip()
                category = input("Book category (blank to skip): ").strip()
                show_records(library.search(kind, query, category))
            elif choice == "6":
                summary = library.summary()
                for key, value in summary.items():
                    print("%s: %s" % (key.replace("_", " ").title(), value))
                if summary["loans_overdue"]:
                    print("WARNING: %d loan(s) are overdue." % summary["loans_overdue"])
                if summary["books_out_of_stock"]:
                    titles = [
                        book["title"]
                        for book in library.data["books"]
                        if book["available_copies"] == CRITICAL_AVAILABLE_COPIES
                    ]
                    print(
                        "CRITICAL: %d title(s) have no copies available: %s"
                        % (summary["books_out_of_stock"], ", ".join(titles))
                    )
            elif choice == "7":
                directory = Path(prompt_text("Export directory: "))
                for path in library.export(directory):
                    print("Wrote %s" % path)
            elif choice == "0":
                print("Library data saved. Goodbye.")
                return
            else:
                print("Choose one of the listed options.")
        except (ValueError, StoreError) as exc:
            print("Error: %s" % exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local library books, members, and loans.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_FILE, help="JSON data file path")
    args = parser.parse_args()
    store = LibraryStore(args.data)
    try:
        store.load()
        run_app(store)
    except (StoreError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\nInterrupted. Changes already saved remain available.", file=sys.stderr)
            return 130
        print("Fatal error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
