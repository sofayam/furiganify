#!/usr/bin/env python3
"""
epub_furigana.py - add furigana (ruby) to every kanji in a Japanese EPUB.

Usage:
    python epub_furigana.py input.epub [output.epub]

If output is omitted, "<input>_furigana.epub" is written next to the input.

Setup (one time, needs internet only for this step):
    pip install lxml fugashi unidic-lite

Behaviour:
  * Kanji that already have <ruby> furigana are left exactly as they are.
  * Every other kanji gets <ruby><rb>漢字</rb><rt>かんじ</rt></ruby>.
  * Okurigana stays outside the ruby: 食べる -> <ruby>食 (た)</ruby>べる
  * Only the book text is changed (XHTML/HTML files). Images, CSS, the
    table of contents, and metadata are copied through untouched.
  * The EPUB must be DRM-free.

Readings come from the UniDic dictionary via fugashi. They are right most of
the time but not always (context-dependent readings, names, wordplay).
Add your own fixes to READING_OVERRIDES below.
"""
import os
import re
import sys
import zipfile

from lxml import etree
from fugashi import Tagger

# surface form -> (analyzer reading, replacement). Edit freely.
# Keys are matched against the whole token, e.g. "日本".
READING_OVERRIDES = {
    "日本": "にほん",
}

XHTML_NS = "http://www.w3.org/1999/xhtml"
KANJI = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u30f6"  # incl. 々 and ヶ
KANJI_RE = re.compile("[%s]" % KANJI)
RUNS_RE = re.compile("[%s]+|[^%s]+" % (KANJI, KANJI))
SKIP_TAGS = {"ruby", "rt", "rb", "rp", "head", "title", "script", "style"}

tagger = Tagger()
unreadable = {}


def kata2hira(s):
    return "".join(
        chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in s
    )


def align(surface, reading):
    """Split a token into (text, reading-or-None) pieces so okurigana stays plain."""
    runs = RUNS_RE.findall(surface)
    if len(runs) == 1:
        return [(surface, reading)]
    pattern = ""
    for run in runs:
        if KANJI_RE.match(run[0]):
            pattern += "(.+?)"
        else:
            pattern += re.escape(kata2hira(run))
    m = re.fullmatch(pattern, reading)
    if not m:  # alignment failed: put the whole reading over the whole token
        return [(surface, reading)]
    out, group = [], 1
    for run in runs:
        if KANJI_RE.match(run[0]):
            out.append((run, m.group(group)))
            group += 1
        else:
            out.append((run, None))
    return out


def segments(text):
    """Return [(text, reading-or-None), ...] for a plain string."""
    segs = []
    for tok in tagger(text):
        surface = tok.surface
        if not KANJI_RE.search(surface):
            segs.append((surface, None))
            continue
        kana = getattr(tok.feature, "kana", None)
        if surface in READING_OVERRIDES:
            reading = READING_OVERRIDES[surface]
        elif kana and kana != "*":
            reading = kata2hira(kana)
        else:
            unreadable[surface] = unreadable.get(surface, 0) + 1
            segs.append((surface, None))
            continue
        segs.extend(align(surface, reading))
    merged = []
    for t, r in segs:
        if r is None and merged and merged[-1][1] is None:
            merged[-1] = (merged[-1][0] + t, None)
        else:
            merged.append((t, r))
    return merged


def make_ruby(ns, text, reading):
    ruby = etree.Element("{%s}ruby" % ns if ns else "ruby")
    rb = etree.SubElement(ruby, "{%s}rb" % ns if ns else "rb")
    rb.text = text
    rt = etree.SubElement(ruby, "{%s}rt" % ns if ns else "rt")
    rt.text = reading
    return ruby


def localname(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def process(el, ns):
    name = localname(el)
    if name is None or name in SKIP_TAGS:  # comments, PIs, ruby, head...
        return

    inserted = []
    if el.text and KANJI_RE.search(el.text):
        segs = segments(el.text)
        el.text = None
        for t, r in segs:
            if r is None:
                if inserted:
                    inserted[-1].tail = (inserted[-1].tail or "") + t
                else:
                    el.text = (el.text or "") + t
            else:
                inserted.append(make_ruby(ns, t, r))
        for i, node in enumerate(inserted):
            el.insert(i, node)
    new_ids = {id(n) for n in inserted}

    for child in list(el):
        if id(child) in new_ids:
            continue
        process(child, ns)
        if child.tail and KANJI_RE.search(child.tail):
            segs = segments(child.tail)
            child.tail = None
            idx = el.index(child)
            prev = child
            for t, r in segs:
                if r is None:
                    prev.tail = (prev.tail or "") + t
                else:
                    node = make_ruby(ns, t, r)
                    idx += 1
                    el.insert(idx, node)
                    prev = node


def convert_document(data):
    parser = etree.XMLParser(resolve_entities=False, remove_blank_text=False)
    tree = etree.fromstring(data, parser).getroottree()
    root = tree.getroot()
    ns = etree.QName(root).namespace or XHTML_NS
    process(root, ns)
    doctype = tree.docinfo.doctype or None
    return etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", doctype=doctype
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.splitext(src)[0] + "_furigana.epub"
    )
    if os.path.abspath(src) == os.path.abspath(dst):
        sys.exit("Output must be a different file from the input.")

    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        if any(n.endswith("META-INF/encryption.xml") for n in names):
            print("Warning: encryption.xml found; font obfuscation is fine, "
                  "but DRM-protected books cannot be processed.")
        # mimetype must come first and be stored uncompressed
        ordered = sorted(names, key=lambda n: 0 if n == "mimetype" else 1)
        with zipfile.ZipFile(dst, "w") as zout:
            for n in ordered:
                data = zin.read(n)
                if n == "mimetype":
                    zout.writestr(n, data, compress_type=zipfile.ZIP_STORED)
                    continue
                if n.lower().endswith((".xhtml", ".html", ".htm")):
                    try:
                        data = convert_document(data)
                        print("converted", n)
                    except etree.XMLSyntaxError as e:
                        print("skipped (not well-formed XML): %s (%s)" % (n, e))
                zout.writestr(n, data, compress_type=zipfile.ZIP_DEFLATED)

    print("\nWrote", dst)
    if unreadable:
        print("No reading found for:", unreadable)


if __name__ == "__main__":
    main()
