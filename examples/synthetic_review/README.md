# Synthetic review example

All content is fictional. The source protocol and background are Markdown text so you can inspect them without additional software; page references are deliberately marked unavailable. The production workflow uses your searchable PDF attachments. This example tests local assembly and evidence handling, not chatbot PDF retrieval or statistical validity.

The draft demonstrates three arms, two named co-primary analysis blocks, an exploratory secondary endpoint, nested bullets, a treatment-arm table, and editable hypotheses. It intentionally retains **Pending reviewer verification** and an open sizing question. The sample sponsor power statement is unverified and must not be treated as an accurate calculation.

The example evidence log maps draft statements and omitted fields to source sections or explicit fictional reviewer decisions. The sponsor request illustrates reviewer-approved wording; one internal explanation is distinct. Approval in this fictional example does not authorize any real review.

`example_report.docx` is a draft and was checked structurally. LibreOffice was unavailable for rendered page QA; inspect its page layout in Word. Build another copy with:

```sh
python3 scripts/review.py build examples/synthetic_review --output output/synthetic-draft.docx
```
