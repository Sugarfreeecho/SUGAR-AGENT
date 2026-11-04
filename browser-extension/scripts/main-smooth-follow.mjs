import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';

export const mainFollowPath=fileURLToPath(new URL('../../frontend/src/app/modules/smooth-stream.js',import.meta.url));
export const followModuleId='virtual:sugaragent-smooth-follow';
// The main UI concatenates this source into its runtime. Export only its
// dependency-free primitives for the extension; no eval or duplicate algorithm.
export async function mainFollowModuleSource(){
  const source=await readFile(mainFollowPath,'utf8');
  const boundary=source.indexOf('const smoothFollowController = createSmoothFollowController();');
  if(boundary<0)throw new Error('Main UI smooth-follow source boundary changed');
  return `const window={__MYAGENT_FEATURES__:{smoothStream:true},matchMedia:query=>globalThis.matchMedia?.(query) || {matches:false}};\n${source.slice(0,boundary)}\nexport {createSmoothFollowController,computeSmoothFollowSpringStep,computeSmoothRevealCount,takeSmoothTextPrefix,SMOOTH_STREAM_CONFIG};`;
}
export function mainSmoothFollowPlugin(){
  const resolved='\0'+followModuleId;
  return {name:'sugaragent-main-smooth-follow',resolveId:id=>id===followModuleId ? resolved : undefined,
    async load(id){if(id!==resolved)return;this.addWatchFile(mainFollowPath);return mainFollowModuleSource();}};
}
