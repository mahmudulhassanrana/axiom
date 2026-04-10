# axiom-exporters

Serializes `axiom_extractors.ExtractedDocument` to:

| Format     | Extension | MIME type              |
| ---------- | --------- | ---------------------- |
| JSON       | `.json`   | `application/json`     |
| CSV        | `.csv`    | `text/csv`             |
| Markdown   | `.md`     | `text/markdown`        |
| HTML       | `.html`   | `text/html`            |

Use `export_bytes(doc, format)` from `axiom_exporters`.
