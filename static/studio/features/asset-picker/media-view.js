import { esc, fmt, bytes } from "../../ui/primitives.js";

export const primaryMedia = (item) =>
  item.snapshot.media.find((m) => m.role === "primary") ||
  item.snapshot.media[0];
export const kindLabel = {
  image: "图片",
  audio: "声音",
  video: "视频",
  workflow: "工作流资料",
};
export function mediaSummary(m) {
  const x = m.meta;
  return [
    kindLabel[x.kind],
    x.width && `${x.width} × ${x.height}`,
    x.duration && `${fmt(x.duration)} 秒`,
    bytes(x.bytes),
  ]
    .filter(Boolean)
    .join(" · ");
}
export function thumbnail(item) {
  const media = primaryMedia(item);
  const url =
    media.preview_url || (media.meta.kind === "image" ? media.url : null);
  return url
    ? `<img loading="lazy" decoding="async" src="${esc(url)}" alt="${esc(item.name)}">`
    : `<span class="library-placeholder" aria-label="${esc(kindLabel[media.meta.kind])}">${media.meta.kind === "audio" ? "♪" : media.meta.kind === "video" ? "▷" : "{ }"}</span>`;
}
export function mediaPlayer(media) {
  const kind = media.meta.kind;
  if (kind === "image")
    return `<div class="library-image-preview"><img src="${esc(media.url)}" alt="${esc(media.name || "资产原图")}"></div>`;
  if (kind === "video")
    return `<video class="library-player" controls preload="metadata" ${media.preview_url ? `poster="${esc(media.preview_url)}"` : ""} src="${esc(media.url)}"></video>`;
  if (kind === "audio")
    return `${media.preview_url ? `<img class="library-wave" src="${esc(media.preview_url)}" alt="音频波形">` : ""}<audio class="library-player" controls preload="metadata" src="${esc(media.url)}"></audio>`;
  return '<div class="notice">工作流附件仅用于查看和导出，不会自动运行。</div>';
}
