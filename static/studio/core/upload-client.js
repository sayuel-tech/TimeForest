/** Upload progress counts transmitted bytes; server processing is a separate phase. */
export function uploadAsset(projectId, file, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const finish = (fn, value) => {
      signal?.removeEventListener("abort", abort);
      fn(value);
    };
    xhr.open("POST", `/api/v5/projects/${projectId}/assets`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) =>
      onProgress({
        loaded: e.loaded,
        total: e.lengthComputable ? e.total : null,
        phase: "上传源视频",
      });
    xhr.upload.onload = () =>
      onProgress({
        loaded: file.size,
        total: file.size,
        phase: "上传完成，服务器正在读取视频信息",
      });
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? finish(resolve, xhr.response)
        : finish(
            reject,
            new Error(xhr.response?.error || `上传失败 ${xhr.status}`),
          );
    xhr.onerror = () => finish(reject, new Error("上传连接中断，请重试"));
    xhr.onabort = () =>
      finish(reject, new DOMException("上传已取消", "AbortError"));
    if (signal?.aborted) {
      reject(new DOMException("上传已取消", "AbortError"));
      return;
    }
    signal?.addEventListener("abort", abort, { once: true });
    const body = new FormData();
    body.append("file", file);
    body.append("kind", "video");
    body.append("purpose", "source");
    xhr.send(body);
  });
}
