/// <reference types="vite/client" />

declare module 'react-force-graph-2d' {
  import { ComponentType } from 'react';
  interface ForceGraph2DProps {
    graphData: {
      nodes: Array<Record<string, unknown>>;
      links: Array<Record<string, unknown>>;
    };
    width?: number;
    height?: number;
    nodeCanvasObject?: (node: Record<string, unknown>, ctx: CanvasRenderingContext2D, globalScale: number) => void;
    linkColor?: (link: Record<string, unknown>) => string;
    linkWidth?: number | ((link: Record<string, unknown>) => number);
    enableNodeDrag?: boolean;
    enableZoomInteraction?: boolean;
    [key: string]: unknown;
  }
  const ForceGraph2D: ComponentType<ForceGraph2DProps>;
  export default ForceGraph2D;
}
