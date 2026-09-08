/** Shared vocabulary; adapters supply their own dirty and operation state. */
export function draftStatus({dirty=false, working=false}={}) {
  return working ? '正在处理，请稍候…' : dirty ? '有未保存修改' : '草稿已保存';
}
