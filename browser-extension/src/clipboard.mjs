export function clipboardFiles(data) {
  const files=Array.from(data?.files || []);
  if(files.length)return files;
  return Array.from(data?.items || []).filter(item=>item.kind==='file').map(item=>item.getAsFile()).filter(Boolean);
}

export function mergeUploads(current,incoming) {
  const merged=new Map(current.map(item=>[item.id,item]));
  for(const item of incoming)merged.set(item.id,item);
  return [...merged.values()];
}
