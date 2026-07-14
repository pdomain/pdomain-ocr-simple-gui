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

it("clicking Choose file triggers the hidden file input", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  renderPicker();
  fireEvent.click(screen.getByRole("button", { name: /choose file/i }));
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("clicking Browse folder triggers the hidden folder input", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  renderPicker();
  fireEvent.click(screen.getByRole("button", { name: /browse folder/i }));
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("drop target is not an interactive button", () => {
  renderPicker();
  const drop = screen.getByTestId("source-picker-drop");
  expect(drop).not.toHaveAttribute("role", "button");
  expect(drop).not.toHaveAttribute("tabindex");
});

it("hidden picker inputs are not keyboard focusable", () => {
  const { container } = renderPicker();
  expect(screen.getByTestId("source-picker-file-pick")).toHaveAttribute(
    "tabindex",
    "-1",
  );
  expect(container.querySelector("input[webkitdirectory]")).toHaveAttribute(
    "tabindex",
    "-1",
  );
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

it("resetToken clears the selected upload display", () => {
  const { rerender } = renderPicker({ resetToken: 0 });

  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(screen.getByTestId("source-picker-drop"), {
    dataTransfer: { files: [file] },
  });
  expect(screen.getByTestId("source-picker-chosen")).toHaveTextContent(
    "scan.png",
  );

  rerender(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      resetToken={1}
      onFilesSelected={() => {}}
      onPathChosen={() => {}}
    />,
  );

  expect(screen.queryByTestId("source-picker-chosen")).toBeNull();
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

it("uses icon source type indicators instead of visible text labels", () => {
  renderPicker();
  expect(screen.getByLabelText("Folder source")).toBeInTheDocument();
  expect(screen.getByLabelText("File source")).toBeInTheDocument();
  expect(screen.getByLabelText("Archive source")).toBeInTheDocument();
  expect(screen.queryByText("DIR")).toBeNull();
  expect(screen.queryByText("FILE")).toBeNull();
  expect(screen.queryByText("ZIP")).toBeNull();
});

it("marks the selected source type icon for regular files", () => {
  renderPicker();
  const file = new File(["x"], "scan-007.jp2", { type: "image/jp2" });
  fireEvent.change(screen.getByTestId("source-picker-file-pick"), {
    target: { files: [file] },
  });
  expect(screen.getByLabelText("File source")).toHaveAttribute(
    "data-selected",
    "true",
  );
  expect(screen.getByLabelText("Folder source")).toHaveAttribute(
    "data-selected",
    "false",
  );
  expect(screen.getByLabelText("Archive source")).toHaveAttribute(
    "data-selected",
    "false",
  );
});

it("marks the archive icon for zip uploads", () => {
  renderPicker();
  const file = new File(["x"], "book.zip", { type: "application/zip" });
  fireEvent.change(screen.getByTestId("source-picker-file-pick"), {
    target: { files: [file] },
  });
  expect(screen.getByLabelText("Archive source")).toHaveAttribute(
    "data-selected",
    "true",
  );
});

it("marks the folder icon for folder uploads", () => {
  renderPicker();
  const file = new File(["x"], "page.png", { type: "image/png" });
  Object.defineProperty(file, "webkitRelativePath", {
    value: "book/page.png",
  });
  fireEvent.change(screen.getByTestId("source-picker-file-pick"), {
    target: { files: [file] },
  });
  expect(screen.getByLabelText("Folder source")).toHaveAttribute(
    "data-selected",
    "true",
  );
});

it("adds files to the current file selection", () => {
  const onFilesSelected = vi.fn();
  renderPicker({ onFilesSelected });
  const input = screen.getByTestId("source-picker-file-pick");
  const first = new File(["a"], "a.jp2", { type: "image/jp2" });
  const second = new File(["b"], "b.jp2", { type: "image/jp2" });

  fireEvent.change(input, { target: { files: [first] } });
  fireEvent.change(input, { target: { files: [second] } });

  expect(onFilesSelected).toHaveBeenLastCalledWith([first, second]);
  expect(screen.getByTestId("source-picker-chosen")).toHaveTextContent(
    "2 files selected",
  );
  expect(
    screen.getByRole("button", { name: /add files/i }),
  ).toBeInTheDocument();
});

it("renders backend-provided size cap and zip in the formats line", () => {
  const { container } = renderPicker({ uploadMaxBytes: 2 * 1024 ** 3 });
  const formats = container.querySelector(".source-picker__formats");
  expect(formats).toHaveTextContent(/ZIP/);
  expect(formats).toHaveTextContent(/max 2 GiB/);
});

it("omits the max-size segment when uploadMaxBytes is absent", () => {
  const { container } = renderPicker();
  const formats = container.querySelector(".source-picker__formats");
  expect(formats).toHaveTextContent(/ZIP/);
  expect(formats).not.toHaveTextContent(/max/);
});

it("removes individual files from the current file selection", () => {
  const onFilesSelected = vi.fn();
  renderPicker({ onFilesSelected });
  const input = screen.getByTestId("source-picker-file-pick");
  const first = new File(["a"], "a.jp2", { type: "image/jp2" });
  const second = new File(["b"], "b.jp2", { type: "image/jp2" });

  fireEvent.change(input, { target: { files: [first, second] } });
  fireEvent.click(screen.getByRole("button", { name: /remove a\.jp2/i }));

  expect(onFilesSelected).toHaveBeenLastCalledWith([second]);
  expect(screen.queryByText("a.jp2")).toBeNull();
  expect(screen.getByText("b.jp2")).toBeInTheDocument();
});
