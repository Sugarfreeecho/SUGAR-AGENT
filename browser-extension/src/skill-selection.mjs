export function skillDisplayMessage(message,names) {
  if(!names.length)return message;
  const suffix='\n\nActivated Skill: '+names.join(', ');
  return message.endsWith(suffix) ? message : message+suffix;
}
