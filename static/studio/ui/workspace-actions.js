/** Shared left support area / right secondary then primary actions. */
export function workspaceActionGroups({support = '', actions = ''}) {
  return `<div class="workspace-support">${support}</div><div class="row workspace-actions">${actions}</div>`;
}
export function workspaceActions(options) {
  return `<footer class="savebar">${workspaceActionGroups(options)}</footer>`;
}
