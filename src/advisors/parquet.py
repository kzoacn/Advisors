from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_PAGES_SCHEMA = pa.schema(
    [
        ("source_url", pa.string()),
        ("university", pa.string()),
        ("department", pa.string()),
        ("fetched_at", pa.string()),
        ("status_code", pa.int64()),
        ("cache_key", pa.string()),
        ("cache_path", pa.string()),
        ("content_hash", pa.string()),
        ("text_hash", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
        ("source_id", pa.string()),
        ("source_type", pa.string()),
    ]
)

TEACHERS_SCHEMA = pa.schema(
    [
        ("profile_id", pa.string()),
        ("person_id", pa.string()),
        ("person_id_status", pa.string()),
        ("identity_confidence", pa.float64()),
        ("name", pa.string()),
        ("university", pa.string()),
        ("department", pa.string()),
        ("lab_or_group", pa.string()),
        ("title", pa.string()),
        ("homepage_url", pa.string()),
        ("source_url", pa.string()),
        ("fetched_at", pa.string()),
        ("page_updated_at", pa.string()),
        ("source_hash", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
    ]
)

TEACHER_NAMES_SCHEMA = pa.schema(
    [
        ("profile_id", pa.string()),
        ("name_value", pa.string()),
        ("name_type", pa.string()),
        ("source_url", pa.string()),
        ("fetched_at", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
    ]
)

TEACHER_ATTRIBUTES_SCHEMA = pa.schema(
    [
        ("profile_id", pa.string()),
        ("attr_key", pa.string()),
        ("attr_value", pa.string()),
        ("source_url", pa.string()),
        ("fetched_at", pa.string()),
        ("confidence", pa.float64()),
        ("extractor", pa.string()),
    ]
)

TEACHER_SECTIONS_SCHEMA = pa.schema(
    [
        ("profile_id", pa.string()),
        ("section_type", pa.string()),
        ("section_title", pa.string()),
        ("section_text", pa.string()),
        ("source_url", pa.string()),
        ("fetched_at", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
    ]
)

DATASET_SCHEMAS = {
    "teachers": TEACHERS_SCHEMA,
    "teacher_names": TEACHER_NAMES_SCHEMA,
    "teacher_attributes": TEACHER_ATTRIBUTES_SCHEMA,
    "teacher_sections": TEACHER_SECTIONS_SCHEMA,
    "source_pages": SOURCE_PAGES_SCHEMA,
}


def write_source_pages(rows: Iterable[dict[str, object]], path: str | Path) -> None:
    write_rows(rows, path, SOURCE_PAGES_SCHEMA)


def write_dataset_tables(tables: dict[str, Iterable[dict[str, object]]], out_dir: str | Path) -> None:
    out_dir = Path(out_dir)
    for table_name, rows in tables.items():
        schema = DATASET_SCHEMAS[table_name]
        write_rows(rows, out_dir / f"{table_name}.parquet", schema)


def write_rows(rows: Iterable[dict[str, object]], path: str | Path, schema: pa.Schema) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row_list = list(rows)
    columns = {
        field.name: [row.get(field.name) for row in row_list]
        for field in schema
    }
    table = pa.Table.from_pydict(columns, schema=schema)
    pq.write_table(table, path)
