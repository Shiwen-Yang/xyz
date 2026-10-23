"""Apply the review style to Pandoc OOXML using only the Python standard library."""
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ET.register_namespace("w", W)
ET.register_namespace("r", R)
ET.register_namespace("m", "http://schemas.openxmlformats.org/officeDocument/2006/math")


def tag(name):
    return f"{{{W}}}{name}"


def put(parent, name, **attributes):
    element = parent.find(tag(name))
    if element is None:
        element = ET.SubElement(parent, tag(name))
    for key, value in attributes.items():
        element.set(tag(key), str(value))
    return element


def spacing(parent, before=0, after=120, line=264):
    put(parent, "spacing", before=before, after=after, line=line, lineRule="auto")


def order_properties(tree):
    """Keep added properties in OOXML schema order, including in Word's strict readers."""
    orders = {
        "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange",
        "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange",
        "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange",
        "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark headers cellIns cellDel cellMerge tcPrChange",
        "trPr": "cnfStyle divId gridBefore gridAfter wBefore wAfter cantSplit trHeight tblHeader tblCellSpacing jc hidden ins del trPrChange",
        "sectPr": "headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange",
    }
    for local, names in orders.items():
        positions = {tag(name): index for index, name in enumerate(names.split())}
        for parent in tree.iter(tag(local)):
            parent[:] = sorted(parent, key=lambda element: positions.get(element.tag, 999))


def customize(source, destination, reference=False):
    """Keep Pandoc's editable lists/math; set styles, numbering, and exact table geometry."""
    with ZipFile(source) as archive:
        files = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    styles = ET.fromstring(files["word/styles.xml"])
    body_styles = {"Normal", "BodyText", "FirstParagraph", "Compact", "ListParagraph"}
    for style in styles.findall(tag("style")):
        identity = style.get(tag("styleId"), "")
        if identity not in body_styles | {"Title", "Subtitle", "Heading1", "Heading2", "Heading3", "TableCaption", "Caption"}:
            continue
        paragraph = put(style, "pPr")
        run = put(style, "rPr")
        fonts = put(run, "rFonts", ascii="Calibri", hAnsi="Calibri", eastAsia="Calibri", cs="Calibri")
        for key in list(fonts.attrib):
            if "Theme" in key:
                del fonts.attrib[key]
        put(run, "color", val="000000")
        put(run, "sz", val=22)
        spacing(paragraph)
        put(paragraph, "widowControl", val=1)
        if identity in {"Title", "Subtitle"}:
            put(run, "sz", val=36 if identity == "Title" else 22)
            spacing(paragraph, after=120)
            put(paragraph, "keepNext", val=1)
            put(paragraph, "jc", val="left")
        if identity.startswith("Heading"):
            level = int(identity[-1])
            put(run, "b", val=1)
            put(run, "sz", val=24 if level == 1 else 22)
            spacing(paragraph, before={1: 240, 2: 200, 3: 160}[level], after=120)
            put(paragraph, "keepNext", val=1)
        if identity == "Compact":
            spacing(paragraph, after=160, line=280)
        if identity in {"Caption", "TableCaption"}:
            spacing(paragraph, before=80, after=80)
    order_properties(styles)
    files["word/styles.xml"] = ET.tostring(styles, encoding="utf-8", xml_declaration=True)
    if "word/numbering.xml" in files:
        numbering = ET.fromstring(files["word/numbering.xml"])
        for level in numbering.iter(tag("lvl")):
            depth = int(level.get(tag("ilvl"), "0"))
            paragraph = put(level, "pPr")
            put(paragraph, "ind", left=720 * (depth + 1), hanging=360)
            tabs = put(paragraph, "tabs")
            for child in list(tabs):
                tabs.remove(child)
            put(tabs, "tab", val="num", pos=720 * (depth + 1))
            spacing(paragraph, after=160, line=280)
        order_properties(numbering)
        files["word/numbering.xml"] = ET.tostring(numbering, encoding="utf-8", xml_declaration=True)
    document = ET.fromstring(files["word/document.xml"])
    if reference:
        body = document.find(tag("body"))
        for child in list(body):
            if child.tag != tag("sectPr"):
                body.remove(child)
        body.insert(0, ET.Element(tag("p")))
    for section in document.iter(tag("sectPr")):
        put(section, "pgSz", w=12240, h=15840)
        put(section, "pgMar", top=1440, right=1440, bottom=1440, left=1440,
            header=708, footer=708, gutter=0)
    for paragraph in document.iter(tag("p")):
        paragraph_properties = paragraph.find(tag("pPr"))
        if paragraph_properties is None:
            continue
        numbering = paragraph_properties.find(tag("numPr"))
        if numbering is not None:
            level = numbering.find(tag("ilvl"))
            depth = int(level.get(tag("val"), "0")) if level is not None else 0
            put(paragraph_properties, "ind", left=720 * (depth + 1), hanging=360)
            spacing(paragraph_properties, after=160, line=280)
    for table in document.iter(tag("tbl")):
        properties = put(table, "tblPr")
        put(properties, "tblW", w=9360, type="dxa")
        put(properties, "tblInd", w=120, type="dxa")
        put(properties, "tblLayout", type="fixed")
        margins = put(properties, "tblCellMar")
        for side, width in (("top", 80), ("bottom", 80), ("left", 120), ("right", 120)):
            put(margins, side, w=width, type="dxa")
        borders = put(properties, "tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            put(borders, side, val="single", sz=4, color="B7B7B7")
        grid = table.find(tag("tblGrid"))
        if grid is None or not len(grid):
            raise ValueError("Table has no column grid")
        existing = [max(1, int(column.get(tag("w"), "1"))) for column in grid]
        widths = [round(9360 * width / sum(existing)) for width in existing]
        widths[-1] += 9360 - sum(widths)
        for column, width in zip(grid, widths):
            column.set(tag("w"), str(width))
        for row_index, row in enumerate(table.findall(tag("tr"))):
            row_properties = put(row, "trPr")
            put(row_properties, "cantSplit")
            if row_index == 0:
                put(row_properties, "tblHeader")
            cells = row.findall(tag("tc"))
            if len(cells) != len(widths):
                raise ValueError("Only rectangular tables without merged cells are supported")
            for cell, width in zip(cells, widths):
                cell_properties = put(cell, "tcPr")
                put(cell_properties, "tcW", w=width, type="dxa")
                put(cell_properties, "vAlign", val="center")
                if row_index == 0:
                    put(cell_properties, "shd", fill="F2F4F7", val="clear")
                for paragraph in cell.findall(tag("p")):
                    spacing(put(paragraph, "pPr"), after=80)
    order_properties(document)
    files["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    # Strip package author metadata; the report's visible author is supplied explicitly.
    if "docProps/core.xml" in files:
        core = ET.fromstring(files["docProps/core.xml"])
        for name in ("{http://purl.org/dc/elements/1.1/}creator",
                     "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy"):
            for element in core.findall(name):
                element.text = ""
        files["docProps/core.xml"] = ET.tostring(core, encoding="utf-8", xml_declaration=True)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
