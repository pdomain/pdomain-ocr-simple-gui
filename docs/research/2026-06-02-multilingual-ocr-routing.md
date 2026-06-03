# Multilingual OCR Routing Research

Date: 2026-06-02

## Current Decision

`pdomain-ocr-simple-gui` keeps the language field simple for now:

- The UI presents English as `en`.
- When the selected engine is Tesseract, runtime logic maps `en` to Tesseract's `eng`.
- English is the only supported Tesseract language in the simple GUI path for now.
- `osd` is not treated as an OCR language. It is Tesseract's orientation/script detection data.

This is intentionally narrower than Tesseract itself. Tesseract supports many language and script traineddata files, but the app is not yet modeling language/script compatibility as a first-class OCR profile.

## Why `en -> eng`

Tesseract uses language data files such as `eng.traineddata`, and its command line examples pass English as `-l eng`. The Tesseract docs also describe `osd.traineddata` separately as orientation and script detection data, not as a language model for text recognition.

The local runtime failure that triggered this note had installed Tesseract languages:

```text
eng, osd
```

The app submitted:

```text
language=en
```

That failed because `en.traineddata` was not installed. The current fix maps `en` to `eng` at submit/dispatch boundaries.

## Future Design: Script-First OCR Profiles

The next multilingual design should not be a larger free-text language field. OCR model behavior often depends on writing system, character inventory, text direction, and engine-specific model packaging.

Recommended future profile shape:

```ts
type OcrProfile = {
  script: "auto" | "Latn" | "Cyrl" | "Arab" | "Deva" | "Hans" | "Hant";
  language: "auto" | "en" | "fr" | "de" | "ar" | "hi" | "zh";
  enginePreference: "auto" | "doctr" | "tesseract" | "paddleocr";
  resolvedEngine: "doctr" | "tesseract" | "paddleocr";
  resolvedEngineLanguage: string;
};
```

Examples:

| User choice | Tesseract resolution | Notes |
| --- | --- | --- |
| English / Latin | `eng` | Current supported path. |
| Auto / Latin | `script/Latin` or specific language | Requires a real script-data policy. |
| Arabic / Arabic | `ara` | Needs RTL-aware post-processing and UI review. |
| Chinese / Simplified | `chi_sim` | Should be modeled separately from Traditional Chinese. |
| Serbian / Cyrillic | engine-specific code | Different from Serbian Latin even when language is similar. |

## Statechart Fit

The job creation machine should eventually own OCR profile resolution, not just source selection and submit state.

Potential states:

```text
configuring
  resolvingProfile
  compatible
  needsLanguageInstall
  unsupportedByEngine
  readyToSubmit
```

Context should include:

```ts
{
  requestedLanguage: string;
  requestedScript: string;
  enginePreference: string;
  installedEngineCapabilities: EngineCapabilities[];
  resolvedEngine: string;
  resolvedLanguageCode: string;
  compatibilityMessage: string | null;
}
```

Regression tests should cover:

- `en + Tesseract + eng installed -> submit eng`
- `en + Tesseract + only osd installed -> needsLanguageInstall`
- `Latin + Auto engine + Tesseract unavailable -> DocTR or unsupported`
- `Arabic + Tesseract + ara missing -> needsLanguageInstall`
- `Arabic + Auto engine + ara installed -> select a compatible engine`

## Engine Notes

### Tesseract

Tesseract language selection is traineddata-file based. The official docs use three-letter language codes such as `eng`, and installation examples include packages such as `tesseract-ocr-eng`, `tesseract-ocr-ara`, and script packages such as `tesseract-ocr-script-latn`.

Useful references:

- [Tesseract command line usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
- [Tesseract installation language data notes](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- [Tesseract data files](https://tesseract-ocr.github.io/tessdoc/tess3/Data-Files.html)

### DocTR

DocTR exposes OCR predictors as detection plus recognition model combinations. Its API includes orientation and language detection options, but the simple GUI currently treats DocTR as the default general OCR path instead of a language-specific runtime.

Useful reference:

- [docTR model API](https://mindee.github.io/doctr/modules/models.html)

### PaddleOCR

PaddleOCR is a candidate for future multilingual routing because PP-OCRv5 documents multilingual recognition models and language abbreviations. Its model registry is closer to the script/language routing shape this app would need than a single free-text language field.

Useful references:

- [PP-OCRv5 multilingual recognition docs](https://www.paddleocr.ai/v3.3.0/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html)
- [PaddleOCR multilingual model source docs](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md)

## Existing Labeled Dataset Candidates

Dataset selection should follow the pipeline stage we want to improve:

- Text recognition needs image crops or page regions paired with exact
  transcription.
- Layout routing needs page-level boxes, reading order, region class labels, or
  PAGE/ALTO XML.
- Script/language routing needs labels that identify script or language at the
  word, line, region, or page level.
- Business-document extraction datasets are useful for end-to-end QA, but often
  less useful for training a general OCR recognizer.

### Best Immediate Fits

| Dataset | Best use | Labels | Languages/scripts | Access/licensing notes |
| --- | --- | --- | --- | --- |
| OCR-D Ground Truth Repository | Historical printed book/page OCR evaluation; PAGE-XML parser fixtures | PAGE-XML GT, multiple annotation depths | Mostly historical German/Latin print, 1500-1900 corpus focus | Public OCR-D GT repository; indexed and downloadable through OCR-D tooling. |
| IMPACT KB Ground Truth | Historical books/newspapers/parliament/radio bulletin evaluation | TIF images plus PAGE XML with text and layout GT | European historical collection material | KB lists copyright as Public Domain/CC0; large TIF/XML archives by category. |
| GT4HistOCR | Tesseract/OCRopy recognizer training for historical print | Line image plus `.gt.txt` transcription pairs | German Fraktur and Early Modern Latin | Zenodo, CC-BY-4.0; 313,173 line pairs; avoid mixing all subcorpora blindly because guidelines differ. |
| HTR-United catalog | Dataset discovery and metadata normalization for OCR/HTR corpora | Catalog links to PAGE XML, ALTO XML, image/TXT pairs | Broad, including printed, handwritten, historical, multilingual | Catalog, not one dataset; requires checking each linked dataset's license and availability. |
| PRImA Layout Analysis Dataset | Layout analysis and PAGE XML tooling | Detailed layout ground truth | Contemporary complex documents | Good for layout/routing, not a full OCR text recognizer dataset by itself. |

### Modern Document/Layout Datasets

| Dataset | Best use | Labels | Languages/scripts | Access/licensing notes |
| --- | --- | --- | --- | --- |
| DocLayNet | General document layout routing and segmentation | COCO-format boxes for 11 layout classes | Finance, science, patents, tenders, law, manuals; language mix depends on source docs | Public dataset; 80,863 human-annotated pages. |
| PubLayNet | Scientific-document layout pretraining/baselines | COCO object-detection annotations | Scientific/PubMed Central articles | Large, automatically matched from XML/PDF; less layout-varied than DocLayNet. |
| FUNSD | Noisy scanned form understanding and word box handling | Word OCR labels, boxes, semantic entities, links | English forms | 199 images; research/educational/non-commercial use; useful for forms, not enough for recognizer training. |
| SROIE / ICDAR 2019 receipts | Receipt OCR and key extraction smoke tests | Quadrilateral word boxes, transcripts, key fields | Primarily English receipts with some multilingual elements | About 1,000 receipt images; CC-BY-4.0 variants exist on Hugging Face/FiftyOne. |

### Scene Text / Natural Image OCR

These are less aligned with scanned books, but useful for testing detection,
cropped-word recognition, arbitrary orientation, and script classification.

| Dataset | Best use | Labels | Languages/scripts | Access/licensing notes |
| --- | --- | --- | --- | --- |
| ICDAR 2019 MLT | Script/language routing stress test | Detection, cropped-word script classification, end-to-end OCR tasks | 10 languages, 7 scripts; real and synthetic sets | RRC challenge dataset; 20,000 real scene images plus synthetic training material. |
| COCO-Text | English/non-English scene-text detection/recognition | Boxes, transcriptions for legible text, printed/handwritten, legibility flags | English-script and non-English-script labels | Annotation license listed as CC-BY-4.0; based on MS COCO images. |
| TextOCR | Large-scale word-level scene OCR benchmark | Polygon/word annotations in COCO-like JSON | Mostly natural-image scene text; language mix must be checked from data | About one million word annotations; good for OCR+VQA-style downstream reasoning, less page-document oriented. |
| IIIT 5K-Word | Cropped word recognition smoke tests | Cropped word images, word GT, lexicons, character boxes | English scene/born-digital words | Small but standard recognizer benchmark; not useful for page layout. |
| PaddleOCR listed public datasets | Integration reference for recognition/detection training format | PaddleOCR conversion format, links to ICDAR, CTW1500, Total-Text, English benchmark bundles | Mostly scene text; depends on listed dataset | Useful to bootstrap import scripts because Paddle documents its expected label format. |

### Handwriting / HTR Datasets

These are not immediate fits for the current printed-OCR GUI, but they matter if
we later route handwritten manuscripts differently from printed pages.

| Dataset | Best use | Labels | Languages/scripts | Access/licensing notes |
| --- | --- | --- | --- | --- |
| Bentham Dataset R0 | Handwritten historical manuscript OCR/HTR | Images plus PAGE-format line-level layout/transcription GT | English handwriting | Zenodo, CC-BY-4.0; research-oriented benchmark. |
| READ-BAD and related READ/Transkribus corpora | Baseline detection and challenging manuscript layout | Baseline/layout annotations, manuscript line structures | Historical manuscripts, multilingual depending on corpus | Useful for segmentation/routing, not simple OCR text extraction. |
| HTR-United catalog entries | Discover smaller language/script corpora | Varies: PAGE XML, ALTO XML, image/TXT pairs | Broad catalog, includes under-resourced scripts/languages | Treat as discovery layer; evaluate licenses per dataset. |

## Dataset Triage Recommendation

For `pdomain-ocr-simple-gui`, prioritize datasets in this order:

1. **OCR-D + IMPACT + GT4HistOCR** for scanned historical/printed document
   recognition and PAGE XML ingestion.
2. **DocLayNet + PRImA** for layout routing and deciding when a page needs
   layout-aware OCR behavior.
3. **SROIE + FUNSD** for end-to-end UI smoke tests around word boxes,
   transcripts, forms, and field extraction style outputs.
4. **ICDAR MLT + COCO-Text/TextOCR/IIIT5K** only for future script routing or
   scene-text robustness; these are not representative of book scans.
5. **HTR-United/Bentham/READ-BAD** only after handwriting is explicitly in
   scope.

The first concrete importer should target PAGE XML because it covers OCR-D,
IMPACT, PRImA, and Bentham-style ground truth. A second importer can handle
COCO-style boxes for DocLayNet, PubLayNet, COCO-Text, and related scene-text
datasets.

## Open Questions

- Should OCR profile selection be exposed as simple `Language` plus advanced `Script`, or as a combined `OCR profile` picker?
- Should `Auto` run script detection first, or should it only mean "choose the best compatible installed engine for the selected profile"?
- Should the backend persist the requested profile and the resolved engine code separately?
- How should mixed-script pages be handled: one project-level profile, per-page detection, or per-region recognition?
- Which engines should be allowed in managed/server mode where install state may differ from local mode?

## Dataset Sources

- [OCR-D data](https://ocr-d.de/en/data)
- [OCR-D Ground Truth Repository workflow](https://ocr-d.de/en/ocrd-gt-repo.html)
- [IMPACT KB Ground Truth](https://lab.kb.nl/dataset/ground-truth-impact-project)
- [GT4HistOCR on Zenodo](https://zenodo.org/records/1344132)
- [HTR-United catalog](https://htr-united.github.io/)
- [PRImA Layout Analysis Dataset](https://www.primaresearch.org/datasets/Layout_Analysis)
- [DocLayNet](https://github.com/DS4SD/DocLayNet)
- [PubLayNet](https://github.com/ibm-aur-nlp/PubLayNet)
- [FUNSD repository](https://github.com/crcresearch/FUNSD)
- [SROIE / scanned receipts dataset card](https://docs.voxel51.com/dataset_zoo/datasets_hf/scanned_receipts.html)
- [ICDAR 2019 MLT paper](https://huggingface.co/papers/1907.00945)
- [COCO-Text](https://vision.cornell.edu/se3/coco-text/)
- [TextOCR](https://textvqa.org/textocr/)
- [IIIT 5K-Word](https://tc11.cvc.uab.es/datasets/IIIT%205K-Word_1)
- [PaddleOCR OCR datasets list](https://www.paddleocr.ai/main/en/datasets/ocr_datasets.html)
- [Bentham Dataset R0](https://zenodo.org/records/44519)
