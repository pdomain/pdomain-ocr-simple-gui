// Tests for DropZone component — TDD first pass
// Issue #227

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DropZone } from "./DropZone";

describe("DropZone", () => {
  it("renders the drop zone area", () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    expect(screen.getByTestId("drop-zone")).toBeInTheDocument();
  });

  it("renders a Browse button", () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    expect(screen.getByRole("button", { name: /browse/i })).toBeInTheDocument();
  });

  it("renders a path text field", () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("shows inline error for empty path on blur", async () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    const input = screen.getByRole("textbox");
    // Focus then blur with empty value
    await userEvent.click(input);
    await userEvent.tab();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /path.*required|required|enter a path/i,
    );
  });

  it("shows inline error for invalid path on blur", async () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "   ");
    await userEvent.tab();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("calls onValidPath when a valid-looking path is typed and confirmed", async () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "/home/user/my-scans");
    // Submit via Enter key
    await userEvent.keyboard("{Enter}");
    expect(onValidPath).toHaveBeenCalledWith("/home/user/my-scans");
  });

  it("calls onValidPath on drop event with DataTransfer items", () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    const zone = screen.getByTestId("drop-zone");

    // Simulate a drop with a file-like path
    const dataTransfer = {
      files: [
        { name: "scan.png", path: "/tmp/scan.png" },
      ] as unknown as FileList,
      items: [],
    };

    fireEvent.drop(zone, { dataTransfer });
    // The path field should now have the dropped path and onValidPath called
    expect(onValidPath).toHaveBeenCalledWith("/tmp/scan.png");
  });

  it("does not show error when a valid path is entered", async () => {
    const onValidPath = vi.fn();
    render(<DropZone onValidPath={onValidPath} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "/home/user/scans");
    await userEvent.tab();
    // Should NOT have an alert since path is non-empty
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onValidPath).not.toHaveBeenCalled(); // only called on submit, not blur
  });
});
