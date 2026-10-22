from __future__ import annotations

import copy
import os
import posixpath
import re
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS}
RID = f"{{{REL_NS}}}id"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", REL_NS)


def _col_number(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        return 0
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n


def _col_letters(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out or "A"


def _normalise_target(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return posixpath.normpath(posixpath.join("xl", target))


class XlsxDatabase:
    """Small OOXML reader/writer for this dashboard.

    It intentionally supports only the simple tabular sheets used by the BUV
    dashboard. It uses only Python's standard library, so the local dashboard
    has no pip/package dependency.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if not zipfile.is_zipfile(self.path):
            raise ValueError(f"Not a valid .xlsx ZIP package: {self.path}")
        with zipfile.ZipFile(self.path, "r") as zf:
            self.entries = {name: zf.read(name) for name in zf.namelist()}
        self._shared_strings = self._read_shared_strings()
        self._sheet_paths = self._read_sheet_paths()
        self._roots: dict[str, ET.Element] = {}
        self._headers: dict[str, list[str]] = {}
        self._data_style_ids: dict[str, dict[int, str]] = {}
        self._table_paths: dict[str, list[str]] = {}

    def _read_shared_strings(self) -> list[str]:
        raw = self.entries.get("xl/sharedStrings.xml")
        if not raw:
            return []
        root = ET.fromstring(raw)
        out = []
        for si in root.findall("m:si", NS):
            out.append("".join(t.text or "" for t in si.iterfind(".//m:t", NS)))
        return out

    def _read_sheet_paths(self) -> dict[str, str]:
        wb = ET.fromstring(self.entries["xl/workbook.xml"])
        rels = ET.fromstring(self.entries["xl/_rels/workbook.xml.rels"])
        relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        out = {}
        for sh in wb.findall(".//m:sheets/m:sheet", NS):
            out[sh.attrib["name"]] = _normalise_target(relmap[sh.attrib[RID]])
        return out

    def sheet_names(self) -> list[str]:
        return list(self._sheet_paths)

    def _root(self, sheet: str) -> ET.Element:
        if sheet not in self._sheet_paths:
            raise KeyError(f"Workbook sheet not found: {sheet}")
        if sheet not in self._roots:
            self._roots[sheet] = ET.fromstring(self.entries[self._sheet_paths[sheet]])
        return self._roots[sheet]

    def _related_table_paths(self, sheet: str) -> list[str]:
        if sheet in self._table_paths:
            return self._table_paths[sheet]
        sheet_path = self._sheet_paths[sheet]
        rel_path = posixpath.join(
            posixpath.dirname(sheet_path),
            "_rels",
            posixpath.basename(sheet_path) + ".rels",
        )
        out: list[str] = []
        raw = self.entries.get(rel_path)
        if raw:
            rels = ET.fromstring(raw)
            for rel in rels:
                if rel.attrib.get("Type", "").endswith("/table"):
                    target = rel.attrib.get("Target", "")
                    if target.startswith("/"):
                        table_path = target.lstrip("/")
                    else:
                        table_path = posixpath.normpath(
                            posixpath.join(posixpath.dirname(sheet_path), target)
                        )
                    if table_path in self.entries:
                        out.append(table_path)
        self._table_paths[sheet] = out
        return out

    def _update_related_tables(self, sheet: str, headers: list[str], record_count: int):
        # Excel tables must stay aligned with the sheet range. This matters after
        # browser saves because the dashboard appends/removes rows in the .xlsx.
        last_col = _col_letters(max(1, len(headers)))
        # Keep at least one blank data row for an otherwise empty Excel table.
        last_row = max(2, record_count + 1)
        table_ref = f"A1:{last_col}{last_row}"
        for table_path in self._related_table_paths(sheet):
            root = ET.fromstring(self.entries[table_path])
            root.attrib["ref"] = table_ref
            auto_filter = root.find(f"{{{MAIN_NS}}}autoFilter")
            if auto_filter is not None:
                auto_filter.attrib["ref"] = table_ref
            table_columns = root.find(f"{{{MAIN_NS}}}tableColumns")
            if table_columns is not None:
                table_columns.clear()
                table_columns.attrib["count"] = str(len(headers))
                for idx, header in enumerate(headers, start=1):
                    ET.SubElement(
                        table_columns,
                        f"{{{MAIN_NS}}}tableColumn",
                        {"id": str(idx), "name": str(header or f"Column{idx}")},
                    )
            self.entries[table_path] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )

    def _cell_value(self, cell: ET.Element):
        t = cell.attrib.get("t")
        if t == "inlineStr":
            return "".join(x.text or "" for x in cell.findall(".//m:t", NS))
        v = cell.find("m:v", NS)
        if v is None or v.text is None:
            return ""
        raw = v.text
        if t == "s":
            try:
                return self._shared_strings[int(raw)]
            except Exception:
                return raw
        if t in {"str", "e"}:
            return raw
        # Numeric values: retain integers/floats where simple, otherwise text.
        try:
            if re.fullmatch(r"-?\d+", raw):
                return int(raw)
            if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][+-]?\d+)?", raw):
                return float(raw)
        except Exception:
            pass
        return raw

    def _row_values(self, row: ET.Element) -> dict[int, object]:
        values: dict[int, object] = {}
        for c in row.findall("m:c", NS):
            idx = _col_number(c.attrib.get("r", ""))
            if idx:
                values[idx] = self._cell_value(c)
        return values

    def _headers_for(self, sheet: str) -> list[str]:
        if sheet in self._headers:
            return self._headers[sheet]
        root = self._root(sheet)
        sheet_data = root.find("m:sheetData", NS)
        if sheet_data is None:
            raise ValueError(f"Sheet {sheet} has no sheetData")
        rows = sheet_data.findall("m:row", NS)
        if not rows:
            raise ValueError(f"Sheet {sheet} has no header row")
        vals = self._row_values(rows[0])
        max_idx = max(vals.keys(), default=0)
        headers = [str(vals.get(i, "")).strip() for i in range(1, max_idx + 1)]
        # Trim trailing blanks but preserve internal blanks.
        while headers and not headers[-1]:
            headers.pop()
        self._headers[sheet] = headers
        style_ids: dict[int, str] = {}
        for row in rows[1:]:
            for c in row.findall("m:c", NS):
                idx = _col_number(c.attrib.get("r", ""))
                if idx and "s" in c.attrib and idx not in style_ids:
                    style_ids[idx] = c.attrib["s"]
            if style_ids:
                break
        self._data_style_ids[sheet] = style_ids
        return headers

    def records(self, sheet: str) -> list[dict[str, object]]:
        headers = self._headers_for(sheet)
        root = self._root(sheet)
        sheet_data = root.find("m:sheetData", NS)
        out = []
        for row in sheet_data.findall("m:row", NS)[1:]:
            vals = self._row_values(row)
            rec = {}
            nonblank = False
            for idx, header in enumerate(headers, start=1):
                if not header:
                    continue
                value = vals.get(idx, "")
                if value not in (None, ""):
                    nonblank = True
                rec[header] = value
            if nonblank:
                out.append(rec)
        return out

    def set_records(self, sheet: str, records: list[dict[str, object]]):
        headers = self._headers_for(sheet)
        root = self._root(sheet)
        sheet_data = root.find("m:sheetData", NS)
        rows = sheet_data.findall("m:row", NS)
        header_row = copy.deepcopy(rows[0])
        sheet_data.clear()
        sheet_data.append(header_row)
        style_ids = self._data_style_ids.get(sheet, {})

        for r_idx, record in enumerate(records, start=2):
            row = ET.Element(f"{{{MAIN_NS}}}row", {"r": str(r_idx)})
            for c_idx, header in enumerate(headers, start=1):
                if not header:
                    continue
                value = record.get(header, "")
                if value is None or value == "":
                    continue
                ref = f"{_col_letters(c_idx)}{r_idx}"
                attrs = {"r": ref}
                if c_idx in style_ids:
                    attrs["s"] = style_ids[c_idx]
                if isinstance(value, bool):
                    attrs["t"] = "b"
                    cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", attrs)
                    ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = "1" if value else "0"
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", attrs)
                    ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = str(value)
                else:
                    attrs["t"] = "inlineStr"
                    cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", attrs)
                    is_el = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
                    t_el = ET.SubElement(is_el, f"{{{MAIN_NS}}}t")
                    text = str(value)
                    if text[:1].isspace() or text[-1:].isspace() or "\n" in text:
                        t_el.attrib[XML_SPACE] = "preserve"
                    t_el.text = text
                row.append(cell) if False else None
            sheet_data.append(row)

        # Preserve a blank row 2 for empty sheets that are backed by an Excel table.
        if not records and self._related_table_paths(sheet):
            sheet_data.append(ET.Element(f"{{{MAIN_NS}}}row", {"r": "2"}))

        dim = root.find("m:dimension", NS)
        if dim is not None:
            last_col = _col_letters(max(1, len(headers)))
            last_row = max(2 if self._related_table_paths(sheet) else 1, len(records) + 1)
            dim.attrib["ref"] = f"A1:{last_col}{last_row}"

        self._update_related_tables(sheet, headers, len(records))
        self.entries[self._sheet_paths[sheet]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def save(self, path: str | os.PathLike[str] | None = None):
        target = Path(path) if path else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Serialize any touched sheet roots.
        for sheet, root in self._roots.items():
            self.entries[self._sheet_paths[sheet]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        fd, tmp_name = tempfile.mkstemp(prefix=target.stem + "_", suffix=".xlsx", dir=str(target.parent))
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for name, data in self.entries.items():
                    zf.writestr(name, data)
            if not zipfile.is_zipfile(tmp):
                raise ValueError("Generated workbook package failed ZIP validation")
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def validate_xlsx(path: str | os.PathLike[str], required_sheets=()) -> tuple[bool, str]:
    try:
        db = XlsxDatabase(path)
        missing = [s for s in required_sheets if s not in db.sheet_names()]
        if missing:
            return False, "Missing worksheet(s): " + ", ".join(missing)
        for sheet in required_sheets:
            db._headers_for(sheet)
        return True, "OK"
    except Exception as exc:
        return False, str(exc)
