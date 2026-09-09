from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, FiniteFloat
from app.core.auth import user
from app.repositories.store import get_store, serialize, now
from app.models.deliverables import KINDS

router = APIRouter(prefix='/api', tags=['Transformation tracking'])


class OutcomeInput(BaseModel):
    metric: str = Field(min_length=2,max_length=120)
    unit: str = Field(min_length=1,max_length=50)
    baseline: FiniteFloat
    target: FiniteFloat
    observed: FiniteFloat
    note: str = Field(default='',max_length=2000)


@router.get('/transformation')
def dashboard(account=Depends(user)):
    s = get_store(); output=[]
    for p in s.db.projects.find(s.project_filter(account['id'])):
        pid=str(p['_id']); complete=[]; approved=[]; open_findings=0; assessments={}
        for kind in KINDS:
            item=s.db.artifacts.find_one({'project_id':pid,'kind':kind},sort=[('version',-1)])
            if item and item.get('source_revision',0)==p.get('context_revision',0):
                complete.append(kind)
                if kind in ('business','transformation'):
                    for assessment in item['content'].get('assessments',[]):
                        assessments[assessment['dimension']]={**assessment,'source_kind':kind,'version':item['version']}
                review=s.db.reviews.find_one({'project_id':pid,'kind':kind,'version':item['version']},sort=[('created_at',-1)])
                if review and review['decision']=='approved': approved.append(kind)
                reviews=item.get('ai_reviews',[])
                if reviews: open_findings+=sum(f['requires_revision'] for f in reviews[-1]['findings'])
        output.append({'project':serialize(p),'current_deliverables':complete,'approved_deliverables':approved,
                       'open_design_findings':open_findings,'assessments':list(assessments.values()),'outcomes':serialize(list(s.db.outcomes.find({'project_id':pid}).sort('created_at',-1).limit(20)))})
    return output


@router.post('/projects/{pid}/outcomes',status_code=201)
def outcome(pid:str,body:OutcomeInput,account=Depends(user)):
    s=get_store();p=s.project(pid,account['id'],'write')
    doc={**body.model_dump(),'project_id':pid,'author':account['id'],'created_at':now()}
    doc['_id']=s.db.outcomes.insert_one(doc).inserted_id
    s.activity(p,account['id'],'Outcome measurement recorded',body.metric)
    return serialize(doc)
