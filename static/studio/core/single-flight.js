/** Coalesce repeated commands without mixing domain-specific save content. */
export function singleFlight(owner, key, action, settled = () => {}) {
  if (owner[key]) return owner[key];
  owner[key] = Promise.resolve().then(action).finally(() => {
    owner[key] = null;
    settled();
  });
  return owner[key];
}
