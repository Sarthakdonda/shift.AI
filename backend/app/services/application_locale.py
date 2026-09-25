"""Reviewed built-in UI labels. Domain labels remain in the approved spec language."""
import html
import json

LABELS = {
    'hi': {'Business workspace':'व्यवसाय कार्यक्षेत्र','BUSINESS WORKSPACE':'व्यवसाय कार्यक्षेत्र','Welcome':'स्वागत है','Sign out':'साइन आउट','Sign in to your workspace':'अपने कार्यक्षेत्र में साइन इन करें','Email':'ईमेल','Password':'पासवर्ड','Sign in':'साइन इन','Team accounts':'टीम खाते','Search records':'रिकॉर्ड खोजें','Search':'खोजें','Add record':'रिकॉर्ड जोड़ें','Actions':'कार्य','Edit':'संपादित करें','Delete':'हटाएं','Previous':'पिछला','Next':'अगला','Edit record':'रिकॉर्ड संपादित करें','Choose a record':'रिकॉर्ड चुनें','Save record':'रिकॉर्ड सहेजें','Cancel':'रद्द करें','Role':'भूमिका','Create account':'खाता बनाएं','Yes':'हाँ','No':'नहीं'},
    'gu': {'Business workspace':'વ્યવસાય કાર્યસ્થળ','BUSINESS WORKSPACE':'વ્યવસાય કાર્યસ્થળ','Welcome':'સ્વાગત છે','Sign out':'સાઇન આઉટ','Sign in to your workspace':'તમારા કાર્યસ્થળમાં સાઇન ઇન કરો','Email':'ઈમેલ','Password':'પાસવર્ડ','Sign in':'સાઇન ઇન','Team accounts':'ટીમ ખાતાં','Search records':'રેકોર્ડ શોધો','Search':'શોધો','Add record':'રેકોર્ડ ઉમેરો','Actions':'કાર્યો','Edit':'ફેરફાર','Delete':'કાઢી નાખો','Previous':'પાછળ','Next':'આગળ','Edit record':'રેકોર્ડમાં ફેરફાર','Choose a record':'રેકોર્ડ પસંદ કરો','Save record':'રેકોર્ડ સાચવો','Cancel':'રદ કરો','Role':'ભૂમિકા','Create account':'ખાતું બનાવો','Yes':'હા','No':'ના'},
}


def localize(files, spec):
    language = spec['language'].split('-')[0].lower()
    labels = LABELS.get(language, {})
    markup = files['public/index.html'].replace('<html lang="en">', '<html lang="' + html.escape(spec['language'], quote=True) + '">')
    script = files['public/app.js']
    for english, translated in sorted(labels.items(), key=lambda item: -len(item[0])):
        markup = markup.replace('>' + english + '<', '>' + html.escape(translated) + '<')
        script = script.replace("'" + english + "'", json.dumps(translated, ensure_ascii=False))
    files['public/index.html'] = markup.replace('<title>' + labels.get('Business workspace', 'Business workspace') + '</title>', '<title>' + html.escape(spec['name']) + '</title>')
    files['public/app.js'] = script
