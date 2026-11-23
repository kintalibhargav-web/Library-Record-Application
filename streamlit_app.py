"""Streamlit interface for the local CampusSolve library manager."""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from library_app import (
    CRITICAL_AVAILABLE_COPIES,
    DEFAULT_DATA_FILE,
    Library,
    LibraryStore,
    StoreError,
)

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 10_000


st.set_page_config(page_title="CampusSolve | Library", page_icon="📚", layout="wide")

st.html(
    """
    <style>
      .library-hero {
        position: relative; overflow: hidden; isolation: isolate;
        padding: 1.1rem 1.25rem; margin: .5rem 0 1rem;
        border: 1px solid #8aa99655; border-radius: 18px;
        background: linear-gradient(115deg, #e5f0e6, #f7f2df 70%, #e5f0e6);
        color: #26352b; animation: arrive .55s ease-out both;
      }
      .library-hero::before, .library-hero::after {
        content: '✦'; position: absolute; color: #c17742; opacity: .55;
        animation: drift 5s ease-in-out infinite alternate;
      }
      .library-hero::before { right: 18%; top: 12%; font-size: 1.3rem; }
      .library-hero::after { right: 7%; bottom: 15%; font-size: .85rem; animation-delay: -2s; }
      .library-hero strong { color: #356b50; }
      .mascot-float-card {
        display: flex; align-items: center; gap: .8rem; padding: .75rem .8rem;
        margin: .35rem 0 .7rem; border: 1px solid #ffffff24;
        border-radius: 14px; background: #ffffff12;
      }
      .mascot-float-card .mascot { font-size: 2.45rem; line-height: 1;
        animation: bob 3.2s ease-in-out infinite; }
      .mascot-float-card p { margin: .2rem 0 0; font-size: .88rem; line-height: 1.4; }
      @keyframes bob { 0%, 100% { transform: translateY(0) rotate(-4deg); }
        50% { transform: translateY(-7px) rotate(4deg); } }
      @keyframes drift { from { transform: translate(0, 0) rotate(0); }
        to { transform: translate(-10px, 8px) rotate(28deg); } }
      @keyframes arrive { from { opacity: 0; transform: translateY(7px); }
        to { opacity: 1; transform: translateY(0); } }
      @media (prefers-reduced-motion: reduce) {
        .library-hero, .library-hero::before, .library-hero::after,
        .mascot-float-card .mascot { animation: none !important; }
      }
    </style>
    """
)

CELEBRATION_KEY = "campussolve_celebration"
CELEBRATION_ANIMATION_KEY = "campussolve_celebration_animation"
MASCOT_SPOTLIGHTS = (
    ("🦉 Milo the Owl", "A few pages today can spark a big idea tomorrow."),
    ("🐛 Pip the Bookworm", "A returned book is ready to find its next reader."),
    ("🦊 Fern the Fox", "Curiosity always finds another shelf to explore."),
    ("🐢 Tully the Turtle", "Every small reading step moves your story forward."),
)
st.session_state.setdefault(CELEBRATION_KEY, None)


@st.cache_resource
def get_library() -> Library:
    store = LibraryStore(DEFAULT_DATA_FILE)
    store.load()
    return Library(store)


try:
    library = get_library()
except StoreError as error:
    st.error(f"Library data could not be loaded: {error}")
    st.info("Correct the JSON file or restore a valid backup before restarting the app.")
    st.stop()

celebration = st.session_state.pop(CELEBRATION_KEY, None)
celebration_animation = st.session_state.pop(CELEBRATION_ANIMATION_KEY, "balloons")
if celebration:
    st.toast(celebration, icon=":material/celebration:")
    if celebration_animation == "snow":
        st.snow()
    else:
        st.balloons()


def celebrate(message: str, animation: str = "balloons") -> None:
    st.session_state[CELEBRATION_KEY] = message
    st.session_state[CELEBRATION_ANIMATION_KEY] = animation
    st.rerun()


with st.sidebar:
    st.markdown("## :material/menu_book: CampusSolve")
    st.caption("LOCAL LIBRARY WORKSPACE")
    page = st.radio(
        "Workspace",
        ["Overview", "Books", "Members", "Circulation", "Reports & import"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("MEET YOUR READING CREW")
    spotlight, message = MASCOT_SPOTLIGHTS[
        date.today().toordinal() % len(MASCOT_SPOTLIGHTS)
    ]
    character = spotlight.split(maxsplit=1)[0]
    st.markdown(
        f'<div class="mascot-float-card"><span class="mascot">{character}</span>'
        f'<div><strong>{spotlight}</strong><p>{message}</p></div></div>',
        unsafe_allow_html=True,
    )
    st.caption("A fresh reading spark every day")
    with st.container(border=True):
        if st.button(
            "Start a mascot celebration",
            icon=":material/celebration:",
            width="stretch",
        ):
            celebrate("The CampusSolve crew is cheering you on!")
    st.caption(f"Storage · `{Path(DEFAULT_DATA_FILE).name}`")
    st.caption("Changes save automatically")


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)
    st.markdown(
        '<div class="library-hero"><strong>Your next chapter starts here.</strong> '
        'Every book you care for finds another curious reader.</div>',
        unsafe_allow_html=True,
    )


def dataframe(
    records: list[dict],
    empty_message: str = "No records to display.",
    alt: str = "Library records",
) -> None:
    if records:
        st.dataframe(pd.DataFrame(records), hide_index=True, alt=alt)
    else:
        st.info(empty_message)


def overdue_rows() -> list[dict]:
    today = date.today()
    return [
        loan for loan in library.data["loans"]
        if not loan["return_date"] and date.fromisoformat(loan["due_date"]) < today
    ]


if page == "Overview":
    header("Library overview", "A clear view of your collection, members, and circulation.")
    metrics = library.summary()
    with st.container(horizontal=True):
        for label, value in zip(
            [
                "Book titles",
                "Members",
                "Available copies",
                "On loan",
                "Overdue",
                "Out of stock",
            ],
            [
                metrics["books"],
                metrics["members"],
                metrics["copies_available"],
                metrics["loans_active"],
                metrics["loans_overdue"],
                metrics["books_out_of_stock"],
            ],
        ):
            st.metric(label, value, border=True)
    if metrics["loans_overdue"]:
        st.warning(
            f"{metrics['loans_overdue']} loan(s) are past their due date.",
            title="Overdue loans",
        )
    if metrics["books_out_of_stock"]:
        out_of_stock = [
            book["title"]
            for book in library.data["books"]
            if book["available_copies"] == CRITICAL_AVAILABLE_COPIES
        ]
        st.error(
            "No copies are available for: %s" % ", ".join(out_of_stock),
            title="Critical stock alert",
        )
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Collection by category")
        categories = metrics["categories"]
        if categories:
            category_data = pd.DataFrame(
                [
                    {"Category": category, "Titles": count}
                    for category, count in categories.items()
                ]
            )
            category_chart = (
                alt.Chart(category_data)
                .mark_bar()
                .encode(
                    x=alt.X("Titles:Q", title="Book titles"),
                    y=alt.Y("Category:N", title=None, sort="-x"),
                    tooltip=["Category:N", "Titles:Q"],
                )
                .properties(height=300)
            )
            st.altair_chart(category_chart, alt="Book titles by category")
        else:
            st.info("Add books to see category trends.")
    with right:
        st.subheader("Circulation snapshot")
        st.metric("Average copies per title", f"{metrics['average_copies_per_title']:.1f}")
        st.metric("Total inventory", metrics["copies_total"])
        st.metric("Loans recorded", metrics["loans_total"])
    st.subheader("Overdue loans")
    overdue = overdue_rows()
    if overdue:
        dataframe(overdue, alt="Overdue book loans")
    else:
        st.success("No overdue loans. Everything is on track.")

elif page == "Books":
    header("Book collection", "Search your catalog, filter by category, or add a title.")
    categories = sorted({book["category"] for book in library.data["books"]})
    qcol, ccol = st.columns([2, 1])
    query = qcol.text_input("Search books", placeholder="Title, author, or book ID")
    category = ccol.selectbox("Category", ["All categories", *categories])
    found = library.search("books", query, "" if category == "All categories" else category)
    st.caption(f"{len(found)} title(s)")
    dataframe(found, alt="Book catalog matching the selected filters")
    with st.expander("＋ Add a book"):
        with st.form("add_book", clear_on_submit=True):
            title = st.text_input("Title *")
            author = st.text_input("Author *")
            new_category = st.text_input("Category *")
            copies = st.number_input("Number of copies", min_value=1, max_value=1000, value=1, step=1)
            submitted = st.form_submit_button("Add to collection", type="primary")
        if submitted:
            try:
                book = library.add_book(title, author, new_category, int(copies))
                celebrate(f"🦊 Fern found a new title: {book['title']}.")
            except (ValueError, StoreError) as error:
                st.error(str(error))

elif page == "Members":
    header("Library members", "Keep member records up to date and easy to find.")
    query = st.text_input("Search members", placeholder="Name, email, or member ID")
    records = library.search("members", query)
    st.caption(f"{len(records)} member(s)")
    dataframe(records, alt="Library members matching the search")
    with st.expander("＋ Register a member"):
        with st.form("add_member", clear_on_submit=True):
            name = st.text_input("Full name *")
            email = st.text_input("Email address *")
            submitted = st.form_submit_button("Register member", type="primary")
        if submitted:
            try:
                member = library.add_member(name, email)
                celebrate(f"🦉 Milo welcomes {member['name']} to the library!")
            except (ValueError, StoreError) as error:
                st.error(str(error))

elif page == "Circulation":
    header("Circulation desk", "Check out available books and record returns.")
    active = [loan for loan in library.data["loans"] if not loan["return_date"]]
    active_view = []
    for loan in active:
        book = library._find(library.data["books"], loan["book_id"])
        member = library._find(library.data["members"], loan["member_id"])
        active_view.append({**loan, "book_title": book["title"], "member_name": member["name"],
                            "status": "Overdue" if loan in overdue_rows() else "On loan"})
    st.subheader("Active loans")
    dataframe(active_view, "There are no active loans.", alt="Active book loans")
    first, second = st.columns(2)
    with first:
        st.markdown("#### Check out a book")
        available_books = [b for b in library.data["books"] if b["available_copies"] > 0]
        if not available_books:
            st.info("No books are currently available.")
        elif not library.data["members"]:
            st.info("Register a member before checking out a book.")
        else:
            with st.form("checkout"):
                book_id = st.selectbox("Book", available_books, format_func=lambda b: f"{b['title']} · {b['id']} ({b['available_copies']} available)")
                member_id = st.selectbox("Member", library.data["members"], format_func=lambda m: f"{m['name']} · {m['id']}")
                days = st.number_input("Loan period (days)", min_value=1, max_value=90, value=14)
                submitted = st.form_submit_button("Confirm checkout", type="primary")
            if submitted:
                try:
                    loan = library.checkout(book_id["id"], member_id["id"], int(days))
                    celebrate(
                        f"🐛 Pip is off on a reading adventure! Due {loan['due_date']}.",
                        animation="snow",
                    )
                except (ValueError, StoreError) as error:
                    st.error(str(error))
    with second:
        st.markdown("#### Record a return")
        if active:
            with st.form("return"):
                loan_id = st.selectbox("Active loan", active, format_func=lambda l: f"{l['id']} · {l['book_id']} · due {l['due_date']}")
                submitted = st.form_submit_button("Mark as returned")
            if submitted:
                try:
                    loan = library.return_book(loan_id["id"])
                    celebrate("🐢 Tully says: this book is ready for its next reader!")
                except (ValueError, StoreError) as error:
                    st.error(str(error))
        else:
            st.info("There are no active loans to return.")

elif page == "Reports & import":
    header("Reports & data tools", "Export a snapshot or safely bring in an existing catalog.")
    st.subheader("Download reports")
    report_dir = Path("exports")
    try:
        paths = library.export(report_dir)
        labels = ["Markdown summary", "Plain-text summary", "Books CSV"]
        for path, label in zip(paths, labels):
            st.download_button(f"Download {label}", path.read_bytes(), file_name=path.name,
                               mime="text/csv" if path.suffix == ".csv" else "text/plain",
                               key=f"download_{path.name}")
    except (OSError, StoreError) as error:
        st.error(f"Could not generate reports: {error}")
    st.divider()
    st.subheader("Bulk import books")
    st.caption("CSV columns: title, author, category, total_copies. Each row is validated before it is saved.")
    uploaded = st.file_uploader("Choose a books CSV file", type=["csv"])
    if uploaded:
        if uploaded.size > MAX_IMPORT_BYTES:
            st.error("This file is too large. Choose a CSV file smaller than 10 MB.")
        else:
            try:
                text = uploaded.getvalue().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text))
                required = {"title", "author", "category", "total_copies"}
                if not reader.fieldnames or not required.issubset(
                    {name.strip().lower() for name in reader.fieldnames}
                ):
                    st.error("CSV header must include title, author, category, total_copies.")
                else:
                    normalized = {name.strip().lower(): name for name in reader.fieldnames}
                    accepted, errors = [], []
                    too_many_rows = False
                    for row_number, row in enumerate(reader, start=2):
                        if row_number > MAX_IMPORT_ROWS + 1:
                            too_many_rows = True
                            break
                        try:
                            values = {
                                key: (row.get(column) or "").strip()
                                for key, column in normalized.items()
                            }
                            copies = int(values["total_copies"])
                            if not all(values[key] for key in ("title", "author", "category")):
                                raise ValueError("title, author, and category are required")
                            if not 1 <= copies <= 1000:
                                raise ValueError("total_copies must be from 1 to 1000")
                            accepted.append(
                                {
                                    "title": values["title"],
                                    "author": values["author"],
                                    "category": values["category"],
                                    "copies": copies,
                                }
                            )
                        except (ValueError, TypeError) as error:
                            errors.append(f"Row {row_number}: {error}")
                    if too_many_rows:
                        st.error(f"This CSV exceeds the {MAX_IMPORT_ROWS:,}-row import limit.")
                    st.caption(f"{len(accepted)} valid row(s), {len(errors)} invalid row(s)")
                    if errors:
                        for message in errors[:20]:
                            st.warning(message)
                        if len(errors) > 20:
                            st.caption(f"…and {len(errors) - 20} more invalid rows")
                    if accepted and not too_many_rows and st.button(
                        f"Import {len(accepted)} valid book(s)", type="primary"
                    ):
                        try:
                            for item in accepted:
                                library.add_book(
                                    item["title"],
                                    item["author"],
                                    item["category"],
                                    item["copies"],
                                )
                            celebrate(f"Added {len(accepted)} books to the collection!")
                        except (ValueError, StoreError) as error:
                            st.error(str(error))
            except (UnicodeDecodeError, csv.Error) as error:
                st.error(f"Could not read this CSV: {error}")

