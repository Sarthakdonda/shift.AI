import hashlib
import json
import time
from datetime import timedelta
from pymongo import ReturnDocument
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.errors import AppError
from app.models.deliverables import LANGUAGES
from app.repositories.store import get_store, now
from app.services.gemini_service import get_gemini

router = APIRouter(prefix='/api', tags=['Interface localization'])


class TranslationInput(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=30)


class TranslationOutput(BaseModel):
    translations: list[str]


@router.post('/localization/{language}')
def translate(language: str, body: TranslationInput, account=Depends(user)):
    if language not in LANGUAGES: raise AppError('Unsupported language.', 400)
    catalog=set(json.loads((Path(__file__).resolve().parents[1] / 'core' / 'ui_catalog.json').read_text(encoding='utf-8')))
    if any(text not in catalog for text in body.texts): raise AppError('Only application interface text can be translated.', 400)
    if language=='en': return dict(zip(body.texts,body.texts))
    s=get_store(); output={}; missing=[]
    for text in body.texts:
        key=hashlib.sha256((language+'\0'+text).encode()).hexdigest()
        cached=s.db.ui_translations.find_one({'_id':key})
        if cached: output[text]=cached['translation']
        else: missing.append(text)
    if missing:
        identifier=hashlib.sha256(f"translation:{account['id']}:{int(time.time())//300}".encode()).hexdigest()
        counter=s.db.auth_attempts.find_one_and_update({'_id':identifier},{'$inc':{'count':1},'$setOnInsert':{'expires_at':now()+timedelta(minutes=10)}},upsert=True,return_document=ReturnDocument.AFTER)
        if counter['count']>30: raise AppError('Translation limit reached. Try again in five minutes.',429)
        result=get_gemini().generate_structured(f'Translate these application interface labels faithfully into {LANGUAGES[language]}. Return one translation per entry, preserving order, numbers and placeholders. Do not add explanation or HTML.',missing,TranslationOutput)
        if len(result.translations)!=len(missing) or any(not t.strip() or len(t)>3000 for t in result.translations):
            raise AppError('Interface translation was incomplete. Retry later.',502)
        for text,translated in zip(missing,result.translations):
            key=hashlib.sha256((language+'\0'+text).encode()).hexdigest()
            s.db.ui_translations.update_one({'_id':key},{'$setOnInsert':{'translation':translated,'language':language,'created_at':now()}},upsert=True)
            output[text]=translated
    return output
