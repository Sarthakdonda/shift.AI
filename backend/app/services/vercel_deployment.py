"""Optional Vercel frontend; the verified Render service retains persistent data."""
import json
import re
from pathlib import Path
import httpx
from bson import ObjectId
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now
from app.services.application_generator import digest
from app.services.url_service import fetch_public


def api(method,path,body=None):
    settings=get_settings()
    if not settings.vercel_token:raise AppError('Set VERCEL_TOKEN on the backend first.',503,'deployment_configuration')
    try:
        result=httpx.request(method,'https://api.vercel.com'+path,json=body,headers={'Authorization':'Bearer '+settings.vercel_token},
            params={'teamId':settings.vercel_team_id} if settings.vercel_team_id else None,timeout=30,follow_redirects=False,trust_env=False)
        if not result.is_success:raise AppError('Vercel returned HTTP '+str(result.status_code)+'. Check provider permissions and build logs.',502,'deployment_error')
        return result.json()
    except (httpx.HTTPError,ValueError):raise AppError('Vercel response unavailable. Check provider history before retrying.',502,'deployment_error') from None


def deploy_job(store,pid,actor,deployment_id):
    key={'_id':ObjectId(deployment_id),'project_id':pid}
    row=store.db.application_deployments.find_one(key)
    try:
        store.project(pid,actor,'admin')
        build=store.db.application_builds.find_one({'_id':ObjectId(row['build_id']),'project_id':pid,'status':'ready'})
        render=store.db.application_deployments.find_one({'project_id':pid,'build_id':row['build_id'],'target':{'$ne':'vercel'},'status':'live'},sort=[('created_at',-1)])
        if not build or not render:raise AppError('Deploy and verify this build on Render first.',409)
        upstream=render['live_url'].rstrip('/')
        if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.onrender\.com',upstream):raise AppError('Invalid verified backend origin.',409)
        proxy=(Path(__file__).resolve().parents[1]/'templates'/'vercel_proxy.mjs').read_text('utf-8').replace('__UPSTREAM__',json.dumps(upstream))
        files=[{'file':name,'data':build['files']['public/'+name]} for name in ('index.html','app.js','style.css')]
        files.extend([{'file':'release.json','data':build['files']['release.json']},{'file':'api/proxy.mjs','data':proxy},
            {'file':'vercel.json','data':json.dumps({'rewrites':[{'source':'/health','destination':'/api/proxy?route=health'},{'source':'/api/:route*','destination':'/api/proxy?route=:route*'}],
            'headers':[{'source':'/(.*)','headers':[{'key':'Cache-Control','value':'no-store'},{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Content-Security-Policy','value':"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}]}]})}])
        remote=api('POST','/v13/deployments',{'name':'shift-'+pid,'files':files,'target':'production','projectSettings':{'framework':None}})
        candidate='https://'+remote['url']
        if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.vercel\.app',candidate):raise AppError('Vercel did not return a supported deployment URL.',502)
        store.db.application_deployments.update_one(key,{'$set':{'status':'deploying','provider_id':remote['id'],'candidate_url':candidate,'backend_url':upstream},'$push':{'logs':'Vercel accepted the release. Frontend identity and backend health checks remain pending.'}})
    except Exception as exc:
        store.db.application_deployments.update_one(key,{'$set':{'status':'failed','error':exc.message if isinstance(exc,AppError) else 'Vercel deployment failed. Inspect provider history before retrying.','finished_at':now()}})
    finally:store.update(pid,busy=False)


def refresh(store,row):
    if row['status'] not in ('deploying','health_pending'):return row
    remote=api('GET','/v13/deployments/'+row['provider_id']);state=remote.get('readyState')
    values={'provider_status':state,'checked_at':now()}
    if state in ('ERROR','CANCELED'):values.update(status='failed',error='Vercel reported '+state+'. Inspect its build logs.')
    elif state=='READY':
        values['status']='health_pending'
        try:
            raw,_,_=fetch_public(row['candidate_url']+'/health',max_bytes=10000,content_types=('application/json',),redirects=0)
            release,_,_=fetch_public(row['candidate_url']+'/release.json',max_bytes=10000,content_types=('application/json',),redirects=0)
            health,identity=json.loads(raw),json.loads(release)
            build=store.db.application_builds.find_one({'_id':ObjectId(row['build_id'])})
            if health.get('status')=='ok' and all(v.get('build_id')==row['build_id'] and v.get('spec_hash')==digest(build['spec']) for v in (health,identity)):
                values.update(status='live',live_url=row['candidate_url'],error=None,finished_at=now())
            else:values['error']='The frontend and backend have not confirmed this exact build.'
        except (AppError,ValueError):values['error']='Vercel is ready; release health remains unverified.'
    store.db.application_deployments.update_one({'_id':row['_id']},{'$set':values})
    return {**row,**values}
