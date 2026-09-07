import { api } from "../../core/api-client.js";

export const libraryApi = (path, method, body, signal) =>
  api("/library" + path, method, body, signal);

/** Each request contains at most 8MB; resume from the server's offset after interruption. */
export async function uploadToLibrary(
  file,
  metadata,
  progress,
  signal,
  target = {},
) {
  const storageKey = `tf-library-upload:${file.name}:${file.size}:${file.lastModified}:${target.asset || "new"}`;
  let upload;
  const prior = sessionStorage.getItem(storageKey);
  if (prior) {
    try {
      upload = await libraryApi(
        "/upload-sessions/" + prior,
        "GET",
        undefined,
        signal,
      );
    } catch (error) {
      if (error.name === "AbortError") throw error;
    }
  }
  if (!upload) {
    upload = await libraryApi(
      "/upload-sessions",
      "POST",
      { name: file.name, size: file.size, metadata, ...target },
      signal,
    );
    sessionStorage.setItem(storageKey, upload.token);
  }
  if (upload.state === "receiving") {
    while (upload.offset < file.size) {
      const end = Math.min(file.size, upload.offset + upload.chunk_bytes);
      const response = await fetch(
        `/api/v5/library/upload-sessions/${upload.token}?offset=${upload.offset}`,
        {
          method: "PUT",
          body: file.slice(upload.offset, end),
          signal,
          headers: { "Content-Type": "application/octet-stream" },
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "分块上传失败，可以重试续传");
      upload = data;
      progress?.(upload.offset / file.size, "上传原件");
    }
  }
  const task = await libraryApi(
    `/upload-sessions/${upload.token}/complete`,
    "POST",
    {},
    signal,
  );
  sessionStorage.removeItem(storageKey);
  return task;
}

export async function followTask(task, onProgress, signal) {
  while (!["done", "failed", "interrupted"].includes(task.state)) {
    onProgress?.(task);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(done, 650);
      function done() {
        signal?.removeEventListener("abort", abort);
        resolve();
      }
      function abort() {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      }
      if (signal?.aborted) abort();
      else signal?.addEventListener("abort", abort, { once: true });
    });
    task = await libraryApi("/tasks/" + task.id, "GET", undefined, signal);
  }
  onProgress?.(task);
  if (task.state !== "done") throw new Error(task.note);
  return task.result;
}
