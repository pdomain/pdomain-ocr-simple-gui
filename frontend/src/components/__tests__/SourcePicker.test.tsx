// Tests for presentational SourcePicker source selection.
import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { SourcePicker } from "../SourcePicker";

function renderPicker(
  props: Partial<ComponentProps<typeof SourcePicker>> = {},
) {
  return render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onFilesSelected={() => {}}
      onPathChosen={() => {}}
      {...props}
    />,
  );
}

it("calls onFilesSelected for a dropped file without fetching", () => {
  const onFilesSelected = vi.fn();
  const fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;

  renderPicker({ allowPathInput: true, onFilesSelected });
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });

  expect(onFilesSelected).toHaveBeenCalledWith([file]);
  expect(fetchSpy).not.toHaveBeenCalled();
});

it("dropzone keeps a generous min-height from CSS class", () => {
  renderPicker();
  expect(screen.getByTestId("source-picker-drop")).toHaveClass(
    "source-picker__drop",
  );
});

it("emits onPathChosen for path input", () => {
  const onPathChosen = vi.fn();
  renderPicker({
    allowDrop: false,
    allowPathInput: true,
    onPathChosen,
    pathHint: "Folder, image, or zip path",
  });
  const input = screen.getByTestId("source-picker-path-input");
  fireEvent.change(input, { target: { value: "/scans/book1" } });
  fireEvent.submit(input.closest("form")!);
  expect(onPathChosen).toHaveBeenCalledWith("/scans/book1");
});

it("clicking the dropzone triggers the hidden file input", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  renderPicker();
  fireEvent.click(screen.getByTestId("source-picker-drop"));
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("pressing Enter on the dropzone triggers the file input", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  renderPicker();
  fireEvent.keyDown(screen.getByTestId("source-picker-drop"), { key: "Enter" });
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("renders the dropped filename after a drop", () => {
  renderPicker();
  const file = new File(["x"], "scan-007.png", { type: "image/png" });
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files: [file] },
  });
  expect(screen.getByTestId("source-picker-chosen")).toHaveTextContent(
    "scan-007.png",
  );
});

it("lists every dropped file with a count header", () => {
  renderPicker();
  const files = [
    new File(["a"], "a.png", { type: "image/png" }),
    new File(["b"], "b.png", { type: "image/png" }),
    new File(["c"], "c.png", { type: "image/png" }),
  ];
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files },
  });
  const chosen = screen.getByTestId("source-picker-chosen");
  expect(chosen).toHaveTextContent("3 files");
  expect(chosen).toHaveTextContent("a.png");
  expect(chosen).toHaveTextContent("b.png");
  expect(chosen).toHaveTextContent("c.png");
});

it("clear button resets the display and fires onClear without deleting uploads", () => {
  const onClear = vi.fn();
  const fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
  renderPicker({ onClear });

  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files: [file] },
  });
  fireEvent.click(screen.getByTestId("source-picker-clear"));

  expect(onClear).toHaveBeenCalledTimes(1);
  expect(screen.queryByTestId("source-picker-chosen")).toBeNull();
  expect(fetchSpy).not.toHaveBeenCalled();
});

it("clicking the clear button does not re-open the file picker", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  renderPicker();
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files: [file] },
  });
  clickSpy.mockClear();
  fireEvent.click(screen.getByTestId("source-picker-clear"));
  expect(clickSpy).not.toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("shows uploadError prop in the existing alert slot", () => {
  renderPicker({ uploadError: "Upload failed." });
  expect(screen.getByTestId("source-picker-upload-error")).toHaveTextContent(
    "Upload failed.",
  );
});

it("does not emit onPathChosen for empty path", () => {
  const onPathChosen = vi.fn();
  renderPicker({
    allowDrop: false,
    allowPathInput: true,
    onPathChosen,
  });
  const input = screen.getByTestId("source-picker-path-input");
  fireEvent.change(input, { target: { value: "" } });
  fireEvent.submit(input.closest("form")!);
  expect(onPathChosen).not.toHaveBeenCalled();
});

it("does not show chosen state when zero files are dropped", () => {
  renderPicker();
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files: [] },
  });
  expect(screen.queryByTestId("source-picker-chosen")).toBeNull();
});

it("source type labels are non-interactive", () => {
  renderPicker();
  expect(screen.queryByRole("button", { name: /folder source/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /file source/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /archive source/i })).toBeNull();
});
