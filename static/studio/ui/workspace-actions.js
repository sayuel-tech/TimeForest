/** Support actions remain separate from decisions about the current object. */
export function workspaceActionGroups({support = '', actions = ''}) {
  return `<div class="workspace-support">${support}</div><div class="row workspace-actions">${actions}</div>`;
}
export function workspaceActions(options) {
  return `<footer class="savebar" aria-label="当前工作区操作">${workspaceActionGroups(options)}</footer>`;
}
