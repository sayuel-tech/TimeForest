export class ApiError extends Error {
  constructor(message, status, code, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.kind = details.kind || (status === 409 ? 'conflict' : status === 404 ? 'not_found' : 'website');
    this.raw = details.raw ?? message;
  }
}

/** API boundary. Mutations are never retried automatically. */
export async function api(path, method = "GET", body, signal) {
  return requestJson("/api/v5" + path, method, body, signal);
}
export function readLegacyProject(id, signal) {
  return requestJson(
    "/api/projects/" + encodeURIComponent(id),
    "GET",
    undefined,
    signal,
  );
}
async function requestJson(url, method, body, signal) {
  const options = { method, signal, headers: {} };
  if (body instanceof FormData) options.body = body;
  else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try { response = await fetch(url, options); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('暂时无法连接网站，请检查连接后重试。', 0, undefined,
      {kind:'network', raw:error.message || String(error)});
  }
  let raw;
  try { raw = await response.text(); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('网站响应未完整接收，请先核对操作状态。', response.status, undefined,
      {kind:'network', raw:error.message || String(error)});
  }
  let data;
  try { data = raw ? JSON.parse(raw) : {}; }
  catch { data = null; }
  if (!response.ok)
    throw new ApiError(
      typeof data?.error === 'string' ? data.error : `请求失败 ${response.status}`,
      response.status,
      data?.code,
      {kind:data?.error_kind, raw:data?.error_raw ?? raw},
    );
  if (data === null)
    throw new ApiError('网站返回了无法读取的响应，请先核对操作状态。', response.status, undefined,
      {kind:'website', raw});
  return data;
}
