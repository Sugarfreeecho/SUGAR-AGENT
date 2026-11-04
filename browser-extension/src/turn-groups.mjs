// A backend restart creates another run, while the durable user/process group
// stays the same. Group only the presentation: per-run phases and tool/steer
// identities remain independent in the canonical timeline.
import {turnKey} from './conversation-turns.mjs';
export function groupConversationTurns(turns,previous=[]){
  const groups=[],identities=new Set();
  for(const turn of turns){
    const tail=groups.at(-1),prior=tail?.turns.at(-1);
    const append=tail && turn.processGroupId && turn.processGroupId===tail.processGroupId
      && !turn.hasUserMessage && !turn.user && !turn.pending && !prior.final;
    if(append)tail.turns.push(turn);
    else {
      const base=turn.processGroupId?'process:'+turn.processGroupId:'run:'+turnKey(turn);
      const id=identities.has(base)?base+':boundary:'+turnKey(turn):base;
      identities.add(id);groups.push({id,processGroupId:turn.processGroupId,turns:[turn]});
    }
  }
  const existing=new Map(previous.map(group=>[group.id,group]));
  const byRun=new Map(previous.flatMap(group=>group.turns.map(turn=>[turnKey(turn),group])));
  const retained=new Set();
  return groups.map(group=>{
    // Metadata can arrive after an approval/editor is already mounted. Keep
    // its component identity when learning a group or prepending older runs.
    const owner=group.turns.map(turn=>byRun.get(turnKey(turn))).find(old=>old && !retained.has(old.id));
    if(owner)group.id=owner.id;
    if(retained.has(group.id))group.id+=':boundary:'+turnKey(group.turns[0]);
    retained.add(group.id);
    const old=existing.get(group.id);
    return old && old.processGroupId===group.processGroupId && old.turns.length===group.turns.length
      && old.turns.every((turn,index)=>turn===group.turns[index])?old:group;
  });
}
