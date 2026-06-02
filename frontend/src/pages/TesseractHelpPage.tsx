import { Link } from "react-router-dom";

export default function TesseractHelpPage() {
  return (
    <div className="help-page" data-testid="tesseract-help-page">
      <div className="help-page__body">
        <Link to="/" className="help-page__back">
          Back
        </Link>
        <h1>Tesseract setup</h1>
        <p>
          Tesseract appears in OCR options only when the app can find the
          Tesseract executable and installed language data.
        </p>
        <h2>Install Tesseract</h2>
        <pre>
          <code>{`# Debian / Ubuntu
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng

# macOS
brew install tesseract`}</code>
        </pre>
        <h2>Language codes</h2>
        <p>
          This simple GUI currently supports English only for Tesseract. The app
          accepts <code>en</code> in the job form and sends Tesseract the code{" "}
          <code>eng</code>.
        </p>
        <h2>Custom tessdata</h2>
        <p>
          If your language files are not in the system tessdata directory, set{" "}
          <code>TESSDATA_PREFIX</code> to the directory containing the{" "}
          <code>tessdata</code> folder, then restart the app.
        </p>
        <pre>
          <code>{`export TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/`}</code>
        </pre>
        <h2>Containers</h2>
        <p>
          Install the Tesseract packages inside the container image or bind
          mount a valid tessdata directory and set <code>TESSDATA_PREFIX</code>{" "}
          inside the container environment.
        </p>
      </div>
    </div>
  );
}
