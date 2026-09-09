// Data equality and redraw decisions are independent of transport and view state.
export const sameSnapshot = (a,b) => JSON.stringify(a)===JSON.stringify(b);
export function snapshotChange(previous,next,content=value=>value) {
  if(sameSnapshot(previous,next))return 'none';
  return sameSnapshot(content(previous),content(next))?'status':'content';
}
