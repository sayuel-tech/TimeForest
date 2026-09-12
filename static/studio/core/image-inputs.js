// Slot letters are stable identities; removing C must not relabel D in a prompt.
export const imageSlots=Object.freeze([... 'ABCDEFGHI']);
export function visibleImageSlots(task){
  if(task.submode==='text')return [];
  return task.submode==='dual'?imageSlots.filter(role=>role==='A'||role==='B'||Object.hasOwn(task,role)):['A'];
}
