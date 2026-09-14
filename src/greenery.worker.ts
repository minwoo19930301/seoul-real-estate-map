import { buildDecorativeTrees, type GreeneryInput } from './greenery';

self.onmessage = ({ data }: MessageEvent<{ id: number; input: GreeneryInput }>) => {
  try {
    self.postMessage({ id: data.id, trees: buildDecorativeTrees(data.input) });
  } catch {
    self.postMessage({ id: data.id, trees: [] });
  }
};
