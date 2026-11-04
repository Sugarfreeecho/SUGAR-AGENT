export function normalizeResourceReference(source) {
  return source.trim().replaceAll('\\','/');
}

function localDestination(source) {
  if(/^[a-z]:[\\/]/i.test(source) || /^file:\/\//i.test(source))return true;
  if(/^[a-z][a-z0-9+.-]*:/i.test(source) || /^[\\/]{2}/.test(source))return false;
  return /[\\/]/.test(source) || /\.[a-z0-9]{1,12}(?:[#:].*)?$/i.test(source);
}

// Tolerate model-generated local links with an escaped opening parenthesis or
// an unquoted Windows destination containing spaces. Code and math are left to
// Marked's normal lexers; only a complete local resource link is consumed.
/** @type {import('marked').TokenizerExtension} */
export const localResourceLinks={
  name:'localResourceLink',level:'inline',
  start:source=>source.search(/!?\[/),
  tokenizer(source) {
    const head=/^(!?)\[((?:\\.|[^\]\\\n])*)\](\\?)\(/.exec(source);
    if(!head)return;
    let cursor=head[0].length,depth=1,end=-1;
    if(source[cursor]==='<') {
      const angle=source.indexOf('>',cursor+1);
      if(angle<0)return;
      const close=/^\s*\\?\)/.exec(source.slice(angle+1));
      if(!close)return;
      end=angle+1+close[0].length;
    } else for(;cursor<source.length;cursor++) {
      if(source[cursor]==='\n')return;
      if(source[cursor]==='(')depth++;
      if(source[cursor]===')' && --depth===0){end=cursor+1;break;}
    }
    if(end<0)return;
    let destination=source.slice(head[0].length,end-1).trim();
    if(destination.startsWith('<'))destination=destination.slice(1,destination.lastIndexOf('>'));
    else destination=destination.replace(/\s+["'][^"']*["']\s*$/,'');
    if(!localDestination(destination))return;
    if(!head[3] && !/[\\\s]/.test(destination))return;
    const href=normalizeResourceReference(destination),text=head[2];
    return {type:head[1] ? 'image' : 'link',raw:source.slice(0,end),href,title:null,text,
      ...(head[1] ? {} : {tokens:this.lexer.inlineTokens(text)})};
  },
};
