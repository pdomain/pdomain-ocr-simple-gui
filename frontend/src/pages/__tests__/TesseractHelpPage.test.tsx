import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import TesseractHelpPage from "../TesseractHelpPage";

it("explains how to install Tesseract language data", () => {
  renderWithProviders(<TesseractHelpPage />);

  expect(screen.getByTestId("tesseract-help-page")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /tesseract setup/i }),
  ).toBeInTheDocument();
  expect(screen.getByText(/tesseract-ocr-eng/i)).toBeInTheDocument();
  expect(screen.getAllByText(/TESSDATA_PREFIX/).length).toBeGreaterThan(0);
});
