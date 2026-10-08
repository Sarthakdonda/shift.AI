"""Reviewed built-in UI labels. Domain labels remain in the approved spec language."""
import html
import json
import hashlib

EXTRA_LABELS = ['No records yet. Add a record or try another search.', 'Delete this record? This cannot be undone.',
    'Initial password (12+ characters)', 'Request failed.', 'Please sign in.', 'Queued', 'Integration deliveries',
    'Your role cannot perform this action.', 'Your role cannot run this workflow action.', 'Administrator access required.',
    'Email or password is incorrect.', 'Request origin is not allowed.', 'Record not found.', 'Not found.',
    'The workflow state changed. Refresh the record.', 'Invalid input. Check required fields, formats, and workflow state.',
    'Duplicate value or referenced record. Check relationships before saving or deleting.',
    'The operation could not complete. Your saved data is preserved.', 'Workspace sign in', 'Contact us']

LABELS = {
    'hi': {'Business workspace':'व्यवसाय कार्यक्षेत्र','BUSINESS WORKSPACE':'व्यवसाय कार्यक्षेत्र','Welcome':'स्वागत है','Sign out':'साइन आउट','Sign in to your workspace':'अपने कार्यक्षेत्र में साइन इन करें','Email':'ईमेल','Password':'पासवर्ड','Sign in':'साइन इन','Team accounts':'टीम खाते','Search records':'रिकॉर्ड खोजें','Search':'खोजें','Add record':'रिकॉर्ड जोड़ें','Actions':'कार्य','Edit':'संपादित करें','Delete':'हटाएं','Previous':'पिछला','Next':'अगला','Edit record':'रिकॉर्ड संपादित करें','Choose a record':'रिकॉर्ड चुनें','Save record':'रिकॉर्ड सहेजें','Cancel':'रद्द करें','Role':'भूमिका','Create account':'खाता बनाएं','Yes':'हाँ','No':'नहीं'},
    'gu': {'Business workspace':'વ્યવસાય કાર્યસ્થળ','BUSINESS WORKSPACE':'વ્યવસાય કાર્યસ્થળ','Welcome':'સ્વાગત છે','Sign out':'સાઇન આઉટ','Sign in to your workspace':'તમારા કાર્યસ્થળમાં સાઇન ઇન કરો','Email':'ઈમેલ','Password':'પાસવર્ડ','Sign in':'સાઇન ઇન','Team accounts':'ટીમ ખાતાં','Search records':'રેકોર્ડ શોધો','Search':'શોધો','Add record':'રેકોર્ડ ઉમેરો','Actions':'કાર્યો','Edit':'ફેરફાર','Delete':'કાઢી નાખો','Previous':'પાછળ','Next':'આગળ','Edit record':'રેકોર્ડમાં ફેરફાર','Choose a record':'રેકોર્ડ પસંદ કરો','Save record':'રેકોર્ડ સાચવો','Cancel':'રદ કરો','Role':'ભૂમિકા','Create account':'ખાતું બનાવો','Yes':'હા','No':'ના'},
}


def localize(files, spec):
    language = spec['language'].split('-')[0].lower()
    allowed = set(LABELS['hi']) | set(EXTRA_LABELS)
    labels = {**LABELS.get(language, {}), **{k: v for k, v in spec.get('ui_labels', {}).items() if k in allowed}}
    markup = files['public/index.html'].replace('<html lang="en">', '<html lang="' + html.escape(spec['language'], quote=True) + '">')
    script = files['public/app.js']
    for english, translated in sorted(labels.items(), key=lambda item: -len(item[0])):
        markup = markup.replace('>' + english + '<', '>' + html.escape(translated) + '<')
        script = script.replace("'" + english + "'", json.dumps(translated, ensure_ascii=False))
    files['public/index.html'] = markup.replace('<title>' + labels.get('Business workspace', 'Business workspace') + '</title>', '<title>' + html.escape(spec['name']) + '</title>')
    files['public/app.js'] = script
    for path, source in list(files.items()):
        if path == 'server.py':
            for english, translated in labels.items():
                source = source.replace(repr(english), json.dumps(translated, ensure_ascii=False))
            files[path] = source
        elif path.startswith('public/site/'):
            for english, translated in labels.items():
                source = source.replace('>' + english + '<', '>' + html.escape(translated) + '<')
            files[path] = source


def translate_labels(store, ai, language):
    from app.api.localization import TranslationOutput
    from app.models.deliverables import LANGUAGES
    if language.split('-')[0].lower() == 'en':
        return {}
    texts = sorted(set(LABELS['hi']) | set(EXTRA_LABELS))
    output = {}
    missing = []
    for text in texts:
        key = hashlib.sha256(('generated-ui:' + language + ':' + text).encode()).hexdigest()
        cached = store.db.ui_translations.find_one({'_id': key})
        if cached:
            output[text] = cached['translation']
        else:
            missing.append(text)
    for offset in range(0, len(missing), 30):
        batch = missing[offset:offset + 30]
        result = ai.generate_structured('Translate every interface label faithfully into ' + LANGUAGES.get(language, language) + '. Return translations in the exact same order. Preserve numbers. Plain text only.', batch, TranslationOutput)
        if len(result.translations) != len(batch) or any(not item.strip() or len(item) > 1500 for item in result.translations):
            raise ValueError('Generated interface translations were incomplete.')
        for text, translated in zip(batch, result.translations):
            key = hashlib.sha256(('generated-ui:' + language + ':' + text).encode()).hexdigest()
            store.db.ui_translations.update_one({'_id': key}, {'$setOnInsert': {'translation': translated, 'language': language}}, upsert=True)
            output[text] = translated
    return output
