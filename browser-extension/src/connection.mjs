import {loopbackUrl} from './shared.mjs';

export function isCurrentConnection(previous, next) {
  return !next.generation || next.generation!==previous?.generation || Number(next.revision)>=Number(previous?.revision ?? -1);
}

// A WebSocket close code can describe a temporary host failure. Confirm the
// credential over HTTP before asking the user to pair again. Never erase it.
export async function verifyPairing(connection, request=fetch) {
  try {
    for (const path of ['/api/browser/v1/connection','/api/browser/v1/models']) {
      const url=loopbackUrl(connection.baseUrl);url.pathname=path;
      const response=await request(url.href,{headers:{Authorization:'Bearer '+connection.token},credentials:'omit',redirect:'error',signal:AbortSignal.timeout(5000)});
      if(response.status===401)return 'invalid';
      if(response.status===404 && path.endsWith('/connection'))continue;
      if(!response.ok)return 'unavailable';
      const body=await response.json();
      if(path.endsWith('/connection'))return body.paired===true && body.browser_id===connection.browserId ? 'valid' : 'unavailable';
      return Array.isArray(body.profiles) ? 'valid' : 'unavailable';
    }
  }catch{}
  return 'unavailable';
}
