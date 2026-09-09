#!/usr/bin/env python3
"""Turn a 5-column 編集台本 TSV into a real Google Docs table.

Pairs with dialogue_cleanup.py --edit-script (which produces the TSV) and sits
opposite platto-automation/tools/push_csv_to_sheet.py, which does the same job
for the rough-cut Sheet. Auth is the `gws` CLI, the same route
platto-automation/tools/script-format.sh already uses -- the repo's own
token.json carries only the spreadsheets scope and cannot write Docs.

Naming matters twice over. gas/Code.js syncScriptUrls() only picks a file up
when the name contains 編集 AND matches #<digits>, so "プラっと#46_編集台本_v1"
registers in the episodes sheet while "プラッと046_編集台本_v8" (no #) and
"プラっと#44" (no 編集) both silently do not.

WHY HTML→Drive CONVERSION rather than the Docs API: building a 362-row table
through documents.batchUpdate means insertTable followed by ~1800 insertText
requests whose indices all shift as you go. Drive converts an uploaded HTML
<table> into a native Docs table in a single request, and the result is a real
table (not a pasted image or preformatted text) that gas/script-tools can walk.

The header row must stay exactly as written: EP039_apply.js finds its target
table by matching the literal "編集指示" in header cell 0, and ScriptFormatter's
findSpeakerCol_() looks for "Speaker Name"/"Speaker"/"話者". Rename either and
the existing Doc tooling silently stops finding the table.
"""
import argparse
import csv
import html
import json
import subprocess
import sys
from pathlib import Path

# 文字起こし列だけ広く。Docs は変換時にこの比率をおおむね維持する。
COL_WIDTHS = ["9%", "8%", "11%", "11%", "61%"]


def build_html(rows: list[list[str]], title: str) -> str:
    out = [
        "<html><head><meta charset='utf-8'></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        "<table border='1' cellspacing='0' cellpadding='4' style='width:100%'>",
    ]
    for i, row in enumerate(rows):
        out.append("<tr>")
        tag = "th" if i == 0 else "td"
        for c, cell in enumerate(row):
            w = f" style='width:{COL_WIDTHS[c]}'" if c < len(COL_WIDTHS) else ""
            out.append(f"<{tag}{w}>{html.escape(cell)}</{tag}>")
        out.append("</tr>")
    out.append("</table></body></html>")
    return "".join(out)


def gws(*args: str, raw: bool = False):
    res = subprocess.run(["gws", *args], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"gws {' '.join(args[:3])} failed:\n{res.stderr}\n{res.stdout}")
    if raw:
        return None
    try:
        out = json.loads(res.stdout)
    except json.JSONDecodeError:
        sys.exit(f"gws {' '.join(args[:3])} returned non-JSON:\n{res.stdout[:500]}")
    if "error" in out:
        sys.exit(f"gws {' '.join(args[:3])} error: {out['error']}")
    return out


def find_existing(title: str, parent: str) -> list:
    """Ids of non-trashed files already named `title` in `parent`."""
    q = (f"name = '{title}' and '{parent}' in parents and trashed = false")
    res = gws("drive", "files", "list",
              "--params", json.dumps({"q": q, "fields": "files(id,name)"}))
    return [f["id"] for f in res.get("files", [])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--title", required=True)
    ap.add_argument("--parent", help="Drive folder id")
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--allow-duplicate", action="store_true",
                    help="create even if a file with this name is already in --parent")
    args = ap.parse_args()

    # QUOTE_NONE, not the default dialect. A transcript cell that merely STARTS
    # with a double quote (ASR does emit them) puts the default reader into
    # quoted-field mode, and it then swallows every following physical line
    # looking for the closing quote: a 4-line file parses as 2 rows, the
    # swallowed speakers and timecodes end up inside one cell, and the script
    # still prints a Doc URL and exits 0. Verified: rows silently disappear
    # from the editor's table with no error anywhere. write_edit_script() never
    # emits CSV quoting, so disabling quote interpretation loses nothing.
    with open(args.tsv, encoding="utf-8") as f:
        rows = [r for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
                if any(x.strip() for x in r)]
    if not rows:
        sys.exit(f"empty TSV: {args.tsv}")
    if rows[0][0].strip() != "編集指示":
        sys.exit(f"header cell 0 must be 編集指示 (EP039_apply.js matches on it), got {rows[0][0]!r}")
    width = len(rows[0])
    for i, r in enumerate(rows):
        if len(r) != width:
            sys.exit(f"{args.tsv} row {i + 1}: {len(r)} columns, header has {width}. "
                     "A short row loses its trailing cells in the Doc without warning.")
    if len(rows) == 1:
        sys.exit(f"{args.tsv} has a header but no data rows")

    if not args.html_only and args.parent:
        dupes = find_existing(args.title, args.parent)
        if dupes and not args.allow_duplicate:
            sys.exit(
                f"'{args.title}' already exists in that folder ({', '.join(dupes)}).\n"
                "gas/Code.js syncScriptUrls() walks the folder in unspecified order and "
                "keeps whichever match it sees last, so a second copy makes script_url "
                "point at a non-deterministic one. Rename with --title, or pass "
                "--allow-duplicate if that is really what you want.")

    tmp = Path(args.tsv).with_suffix(".upload.html")
    tmp.write_text(build_html(rows, args.title), encoding="utf-8")
    print(f"HTML: {tmp}  ({len(rows)-1} データ行 × {width}列)")
    if args.html_only:
        return

    # Two steps on purpose. Uploading media WITH the Docs mimeType in the same
    # request is rejected 400 by Drive through this CLI (the metadata mimeType
    # ends up on the media part). Uploading as text/html and converting on
    # copy is the path that works; the temporary HTML file is then deleted.
    up = gws("drive", "files", "create",
             "--json", json.dumps({"name": f"{args.title}.upload.html"}, ensure_ascii=False),
             "--upload", str(tmp))
    html_id = up["id"]

    body = {"name": args.title, "mimeType": "application/vnd.google-apps.document"}
    if args.parent:
        body["parents"] = [args.parent]
    try:
        doc = gws("drive", "files", "copy",
                  "--params", json.dumps({"fileId": html_id}),
                  "--json", json.dumps(body, ensure_ascii=False))
    finally:
        # Both cleanups belong here: on the failure path the intermediate HTML
        # is exactly what must not be left behind, on Drive or on disk.
        gws("drive", "files", "delete", "--params", json.dumps({"fileId": html_id}), raw=True)
        tmp.unlink(missing_ok=True)

    doc_id = doc["id"]
    print(f"Doc: {args.title}")
    print(f"  id:  {doc_id}")
    print(f"  url: https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == "__main__":
    main()
