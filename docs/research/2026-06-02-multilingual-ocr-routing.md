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

## Open Questions

- Should OCR profile selection be exposed as simple `Language` plus advanced `Script`, or as a combined `OCR profile` picker?
- Should `Auto` run script detection first, or should it only mean "choose the best compatible installed engine for the selected profile"?
- Should the backend persist the requested profile and the resolved engine code separately?
- How should mixed-script pages be handled: one project-level profile, per-page detection, or per-region recognition?
- Which engines should be allowed in managed/server mode where install state may differ from local mode?
