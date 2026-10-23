# Word style contract

Base preset: standard_business_brief. Header pattern: memo_masthead, simplified to a title, submission subtitle, author, and optional date; no cover page or decorative rule.

Named override **statistical_review_template** preserves the compact black hierarchy of the TeX report: Calibri 11 pt body, 1.10 line spacing, 0/6 pt paragraph spacing; black bold Heading 1 at 12 pt with 12/6 pt spacing, Heading 2 at 11 pt with 10/6 pt spacing, Heading 3 at 11 pt with 8/6 pt spacing; left-aligned 18 pt title. The title and headings stay with the following paragraph. Quiet Pandoc reference page furniture is retained; no new running header is required.

US Letter portrait, 1-inch margins, 0.492-inch header/footer distances, usable width 9360 DXA. Real Word list numbering: marker at 0.25 inch, text at 0.5 inch, hanging indent 0.25 inch; each nested level adds 0.5 inch. List spacing is 0/8 pt with 1.167 line spacing.

Tables: fixed 9360-DXA width, 120-DXA indent, proportional column widths from Pandoc's grid, matching grid and cell widths; 80-DXA top/bottom and 120-DXA left/right padding; thin gray grid and light gray header fill. First row repeats as a header. Cells are vertically centered and rows have no fixed height. Caption/source spacing is 4/4 pt. No merged cells or paragraph lists inside cells in v1.

The checked-in reference.docx carries styles/page setup. The build also normalizes actual list numbering and table geometry after Pandoc conversion, since a reference file alone does not guarantee them. A custom --reference-doc may change other styles, but these review-style properties are still applied. Modify scripts/word_style.py to deliberately change the contract.

Structural checks cannot prove page-layout quality. Open the generated report in Word and check every page, especially long rows and equations. This repository's initial artifacts were structurally checked; LibreOffice was unavailable for rendered page QA.
