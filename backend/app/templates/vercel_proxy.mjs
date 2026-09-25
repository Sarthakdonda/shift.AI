// Trusted same-origin gateway. The upstream is a fixed, verified Render release.
const upstream = __UPSTREAM__;
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (!['GET', 'POST', 'DELETE'].includes(request.method)) return Response.json({error:'Method not allowed'}, {status:405});
    if (request.method !== 'GET' && request.headers.get('origin') !== url.origin) return Response.json({error:'Origin rejected'}, {status:403});
    const part = url.searchParams.get('route') || url.pathname.replace(/^\/api\//, '');
    if (!/^(health|login|logout|spec|users|records\/[a-z][a-z0-9_]*(\/[a-zA-Z0-9_-]+)?(\/transition)?)$/.test(part)) return Response.json({error:'Not found'}, {status:404});
    const target = new URL(part === 'health' ? '/health' : '/api/' + part, upstream);
    for (const key of ['q','offset']) if(url.searchParams.has(key)) target.searchParams.set(key,url.searchParams.get(key));
    const headers = {'Content-Type':'application/json', Origin:upstream};
    const cookie = (request.headers.get('cookie') || '').split(';').map(v=>v.trim()).find(v=>/^app_session=[A-Za-z0-9_-]*$/.test(v));
    if (cookie) headers.Cookie = cookie;
    let body;
    if (request.method !== 'GET') {
      if (Number(request.headers.get('content-length') || 0) > 65536) return Response.json({error:'Request too large'}, {status:413});
      const reader = request.body?.getReader(); const parts=[]; let size=0;
      if(reader) while(true) { const {done,value}=await reader.read(); if(done)break;size+=value.length;if(size>65536){await reader.cancel();return Response.json({error:'Request too large'},{status:413});}parts.push(value); }
      body = new Uint8Array(size);let position=0;for(const part of parts){body.set(part,position);position+=part.length;}
    }
    try {
      const response = await fetch(target,{method:request.method,headers,body,redirect:'error',signal:AbortSignal.timeout(15000)});
      const out = new Headers({'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
      const session = response.headers.get('set-cookie'); if(session?.startsWith('app_session='))out.set('Set-Cookie',session);
      return new Response(response.body,{status:response.status,headers:out});
    } catch { return Response.json({error:'Application backend unavailable. Please retry.'},{status:502}); }
  }
};
