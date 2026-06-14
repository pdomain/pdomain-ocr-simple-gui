import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CudaSetupGuidance } from "../CudaSetupGuidance";

describe("CudaSetupGuidance", () => {
  it("renders actionable CUDA configuration guidance inside the app", () => {
    render(<CudaSetupGuidance />);

    expect(
      screen.getByRole("heading", { name: /CUDA setup/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /NVIDIA GPU can be detected even when CUDA is not usable/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/nvidia-smi/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/torch\.cuda\.is_available/i).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: /PyTorch selector/i }),
    ).toHaveAttribute("href", "https://pytorch.org/get-started/locally/");
  });
});
