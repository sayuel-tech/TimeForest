const tools = ['single', 'dual', 'region', 'outpaint'];
const groups = ['core', 'picture', 'sampling', 'assets', 'lora', 'memory', 'advanced'];

/** An old website process can serve new static files without the matching API. */
export function assertImageCatalog(catalog, currentTool) {
  const expected=[...tools,...(catalog?.tools?.text||currentTool==='text'?['text']:[])];
  const valid = catalog?.parameter_contract_version === 1 && (!expected.includes('text')||catalog.text_to_image_version===1) && expected.every(tool => {
    const fields = catalog.parameters?.[tool];
    return Array.isArray(fields) && fields.length > 0 && fields.every(field => field &&
      ['settings', 'models'].includes(field.scope) && typeof field.key === 'string' &&
      typeof field.label === 'string' && groups.includes(field.group) &&
      ['number', 'select', 'model', 'seed'].includes(field.type)) &&
      fields.some(field => field.scope === 'models' && field.key === 'unet' && field.type === 'model') &&
      fields.some(field => field.scope === 'settings' && field.key === 'steps' && field.type === 'number') &&
      fields.some(field => field.scope === 'settings' && field.key === 'seed' && field.type === 'seed');
  });
  if (!valid) throw Object.assign(new Error(
    '图片参数尚未加载：网站前后端版本不一致。请先保存已有编辑，关闭网站服务窗口后重新启动网站，再刷新页面。无需启动 ComfyUI。'
  ), {code: 'IMAGE_PARAMETER_CONTRACT_MISMATCH', kind: 'website'});
  return catalog;
}
