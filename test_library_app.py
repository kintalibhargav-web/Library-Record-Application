import csv
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from library_app import Library, LibraryStore, StoreError, run_app


class LibraryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temp_dir.name) / "library.json"
        self.store = LibraryStore(self.data_path)
        self.store.load()
        self.library = Library(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_data_is_persisted_and_has_demo_records(self):
        self.assertEqual(len(self.library.data["books"]), 30)
        self.assertEqual(len(self.library.data["members"]), 10)
        self.assertEqual(len(self.library.data["loans"]), 5)
        self.assertEqual(json.loads(self.data_path.read_text())["version"], 1)

    def test_checkout_and_return_update_inventory_and_persist(self):
        book_id, member_id = "B0005", "M0001"
        original_count = self.library._find(self.library.data["books"], book_id)["available_copies"]
        loan = self.library.checkout(book_id, member_id, 7)
        self.assertEqual(
            self.library._find(self.library.data["books"], book_id)["available_copies"],
            original_count - 1,
        )
        self.library.return_book(loan["id"])
        self.assertEqual(
            self.library._find(self.library.data["books"], book_id)["available_copies"],
            original_count,
        )
        reloaded = LibraryStore(self.data_path)
        reloaded.load()
        self.assertEqual(reloaded.data["loans"][-1]["return_date"] is not None, True)

    def test_validation_prevents_invalid_checkout_and_duplicate_member(self):
        with self.assertRaises(ValueError):
            self.library.checkout("missing", "M0001")
        with self.assertRaises(ValueError):
            self.library.add_member("Duplicate", "aarav.sharma@example.edu")
        self.assertEqual(self.library.search("books", category="technology")[0]["category"], "Technology")

    def test_out_of_stock_threshold_is_reported_and_clears_on_return(self):
        book = self.library.add_book("Last Copy", "A. Writer", "Testing", copies=1)
        self.library.checkout(book["id"], "M0001")
        self.assertEqual(self.library.summary()["books_out_of_stock"], 1)

        with patch("builtins.input", side_effect=["6", "0"]), patch(
            "sys.stdout", new_callable=StringIO
        ) as output:
            run_app(self.store)
        self.assertIn("CRITICAL: 1 title(s) have no copies available: Last Copy", output.getvalue())

        self.library.return_book(self.library.data["loans"][-1]["id"])
        self.assertEqual(self.library.summary()["books_out_of_stock"], 0)

    def test_corrupt_storage_is_not_overwritten(self):
        self.data_path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(StoreError):
            LibraryStore(self.data_path).load()
        self.assertEqual(self.data_path.read_text(encoding="utf-8"), "{broken")

    def test_exports_include_summary_and_catalog_csv(self):
        output = Path(self.temp_dir.name) / "reports"
        paths = self.library.export(output)
        self.assertEqual(len(paths), 3)
        with paths[2].open(newline="", encoding="utf-8") as file:
            self.assertEqual(len(list(csv.DictReader(file))), 30)
        self.assertIn("Library Summary", paths[0].read_text(encoding="utf-8"))
        self.assertIn("Out-of-stock titles", paths[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
