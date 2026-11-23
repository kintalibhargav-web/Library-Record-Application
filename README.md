# CampusSolve Library Records

A local-first library record application with a Streamlit web interface and a standard-library
terminal interface. Book, member, and loan records persist in `library_data.json`; the app
starts with 30 sample books, 10 members, and 5 sample loans when no data file exists. Matching
CSV datasets for all three record types are in `sample_data/` for review and demo imports.

## Streamlit web interface

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The dashboard includes collection and overdue summaries, book and member search, book and
member registration, book checkout and return workflows, Markdown/text/CSV report downloads,
and validated bulk CSV book import. CSV imports accept `title,author,category,total_copies`;
invalid rows are reported with their source row numbers, and only valid rows can be imported.
CSV imports are limited to 10 MB and 10,000 rows. The web app binds to `127.0.0.1` by default
so the local member records are not exposed to other machines on the network.
The sidebar features four original library mascots—Milo, Pip, Fern, and Tully—with a rotating
daily reading motivation. Successful updates trigger floating balloons, while checkouts add
a snowfall effect. All data is saved locally in JSON; corrupt or invalid JSON is reported
without being overwritten.

## Requirement check

| Problem-brief requirement | Status |
| --- | --- |
| Menu-driven terminal interface and guided workflows | Complete (`library_app.py`) |
| Defensive validation and reliable JSON persistence | Complete |
| Book, member, checkout, and return business workflows | Complete |
| Keyword and category-based record search | Complete |
| Summary metrics, category breakdown, and overdue warnings | Complete |
| Markdown, plain-text, and CSV report exports | Complete |
| CSV bulk import with row-level validation feedback | Complete |
| Streamlit web interface | Complete (`streamlit_app.py`) |
| Motivational mascots and floating success animations | Complete (Streamlit-native balloons and snowfall) |
| Sample library records in JSON and CSV | Complete (30 books, 10 members, 5 loans; CSV copies in `sample_data/`) |
| Critical stock alerts | Complete; a title is critical when zero copies are available |

## Terminal interface

```powershell
python library_app.py
```

The terminal workflow offers the same core catalog, member, circulation, summary, and export
operations. Use `--data C:\path\to\library_data.json` to select a different JSON store.

## Validation

The project includes a `unittest` suite in `test_library_app.py` covering persistence,
checkout/return inventory changes, validation, corrupt storage handling, and exports. Run it with:

```powershell
python -m unittest -v
```
