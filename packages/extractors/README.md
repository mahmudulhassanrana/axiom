# axiom-extractors

Modular extractors that return a **normalized** `ExtractedDocument` (Pydantic) for downstream ingestion.

## Extractors

| Module                | Mechanism                        | Use case                           |
| --------------------- | -------------------------------- | ---------------------------------- |
| `HtmlExtractor`       | `requests` + BeautifulSoup       | Static HTML, server-rendered pages |
| `PlaywrightExtractor` | Playwright (Chromium by default) | Client-rendered / JS-heavy pages   |

Install browser binaries for Playwright once per machine:

```bash
playwright install chromium
```

## Install

From the repository root (or this directory):

```bash
cd packages/extractors
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```python
from axiom_extractors import ExtractedDocument, HtmlExtractor, PlaywrightExtractor

html_ex = HtmlExtractor()
doc: ExtractedDocument = html_ex.extract("https://example.com")
print(doc.model_dump(mode="json"))

js_ex = PlaywrightExtractor()
doc_js = js_ex.extract("https://example.com")
```

## Compliance

Extractors fetch URLs you pass in. **Callers** must enforce `robots.txt`, rate limits, and terms of service before invoking an extractor. This package does not bypass protections.
