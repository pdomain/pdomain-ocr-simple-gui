// pdomain-ui-stages-page-workbench.d.ts — module type shim
//
// @pdomain/pdomain-ui stages/PageWorkbench ships dist/stages/PageWorkbench/index.d.ts
// with `export * from '../../src/stages/PageWorkbench/index'`, which resolves
// correctly when src/ is present (local-dev mode) but fails in the installed
// package where src/ is absent.
//
// This ambient module declaration provides the types needed by PageViewPage.tsx
// without requiring source access. Keep in sync with the ArtifactViewer API.
// Remove once pdomain-ui publishes a package with self-contained .d.ts files.

declare module "@pdomain/pdomain-ui/stages/PageWorkbench" {
  import type * as React from "react";

  export type OverlayMode = "view" | "split" | "illust" | "rotate" | "words";

  export interface WordBbox {
    id: string;
    /** Normalized [x, y, w, h] relative to image dimensions. */
    bbox: [number, number, number, number];
    confidence?: number;
    selected?: boolean;
  }

  export interface IllustBbox {
    id: string;
    bbox: [number, number, number, number];
  }

  export interface SplitProposal {
    splitX: number;
    onSplitXChange?: (x: number) => void;
  }

  export interface ArtifactViewerProps {
    imageSrc: string;
    pageWidth: number;
    pageHeight: number;
    overlayMode?: OverlayMode;
    splitProposal?: SplitProposal;
    illustBboxes?: IllustBbox[];
    wordBboxes?: WordBbox[];
    onWordClick?: (id: string) => void;
    rotationDeg?: number;
    onRotationChange?: (deg: number) => void;
    className?: string;
    extraLayersSlot?: React.ReactNode;
  }

  export declare function ArtifactViewer(
    props: ArtifactViewerProps,
  ): React.ReactElement;
}
