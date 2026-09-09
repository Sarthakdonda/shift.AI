"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { languages } from "@/lib/deliverables";
import { post } from "@/lib/api";
import catalog from "@/lib/ui_catalog.json";
const knownLabels = new Set(catalog);
const keys = [
  "Projects",
  "New project",
  "Discovery",
  "Documents",
  "Analysis",
  "Solution",
  "Red Team",
  "Blueprint",
  "Deliverables",
  "Teams & admin",
  "Transformation",
  "Email address",
  "Password",
  "Full name",
  "Confirm password",
  "Create account",
  "Sign in",
  "Welcome back.",
];
const rows: Record<string, string[]> = {
  hi: [
    "परियोजनाएँ",
    "नई परियोजना",
    "खोज",
    "दस्तावेज़",
    "विश्लेषण",
    "समाधान",
    "रेड टीम",
    "ब्लूप्रिंट",
    "डिलिवरेबल्स",
    "टीम और प्रशासन",
    "परिवर्तन",
    "ईमेल पता",
    "पासवर्ड",
    "पूरा नाम",
    "पासवर्ड की पुष्टि",
    "खाता बनाएँ",
    "साइन इन",
    "वापस स्वागत है।",
  ],
  es: [
    "Proyectos",
    "Nuevo proyecto",
    "Descubrimiento",
    "Documentos",
    "Análisis",
    "Solución",
    "Equipo crítico",
    "Plan detallado",
    "Entregables",
    "Equipos y administración",
    "Transformación",
    "Correo electrónico",
    "Contraseña",
    "Nombre completo",
    "Confirmar contraseña",
    "Crear cuenta",
    "Iniciar sesión",
    "Bienvenido de nuevo.",
  ],
  fr: [
    "Projets",
    "Nouveau projet",
    "Découverte",
    "Documents",
    "Analyse",
    "Solution",
    "Revue critique",
    "Plan détaillé",
    "Livrables",
    "Équipes et administration",
    "Transformation",
    "Adresse e-mail",
    "Mot de passe",
    "Nom complet",
    "Confirmer le mot de passe",
    "Créer un compte",
    "Se connecter",
    "Bon retour.",
  ],
  de: [
    "Projekte",
    "Neues Projekt",
    "Erkundung",
    "Dokumente",
    "Analyse",
    "Lösung",
    "Kritische Prüfung",
    "Bauplan",
    "Ergebnisse",
    "Teams und Verwaltung",
    "Transformation",
    "E-Mail-Adresse",
    "Passwort",
    "Vollständiger Name",
    "Passwort bestätigen",
    "Konto erstellen",
    "Anmelden",
    "Willkommen zurück.",
  ],
  ar: [
    "المشاريع",
    "مشروع جديد",
    "الاستكشاف",
    "المستندات",
    "التحليل",
    "الحل",
    "المراجعة النقدية",
    "المخطط",
    "المخرجات",
    "الفرق والإدارة",
    "التحول",
    "البريد الإلكتروني",
    "كلمة المرور",
    "الاسم الكامل",
    "تأكيد كلمة المرور",
    "إنشاء حساب",
    "تسجيل الدخول",
    "مرحبًا بعودتك.",
  ],
  pt: [
    "Projetos",
    "Novo projeto",
    "Descoberta",
    "Documentos",
    "Análise",
    "Solução",
    "Revisão crítica",
    "Plano detalhado",
    "Entregáveis",
    "Equipes e administração",
    "Transformação",
    "E-mail",
    "Senha",
    "Nome completo",
    "Confirmar senha",
    "Criar conta",
    "Entrar",
    "Bem-vindo de volta.",
  ],
  zh: [
    "项目",
    "新建项目",
    "需求探索",
    "文档",
    "分析",
    "解决方案",
    "红队评审",
    "蓝图",
    "交付成果",
    "团队与管理",
    "转型",
    "电子邮箱",
    "密码",
    "姓名",
    "确认密码",
    "创建账户",
    "登录",
    "欢迎回来。",
  ],
  ja: [
    "プロジェクト",
    "新規プロジェクト",
    "要件探索",
    "文書",
    "分析",
    "ソリューション",
    "批判的レビュー",
    "設計図",
    "成果物",
    "チームと管理",
    "変革",
    "メールアドレス",
    "パスワード",
    "氏名",
    "パスワードの確認",
    "アカウント作成",
    "ログイン",
    "お帰りなさい。",
  ],
  ko: [
    "프로젝트",
    "새 프로젝트",
    "요구 사항 탐색",
    "문서",
    "분석",
    "솔루션",
    "비판적 검토",
    "청사진",
    "산출물",
    "팀 및 관리",
    "혁신",
    "이메일 주소",
    "비밀번호",
    "이름",
    "비밀번호 확인",
    "계정 만들기",
    "로그인",
    "다시 오신 것을 환영합니다.",
  ],
  it: [
    "Progetti",
    "Nuovo progetto",
    "Esplorazione",
    "Documenti",
    "Analisi",
    "Soluzione",
    "Revisione critica",
    "Piano dettagliato",
    "Risultati",
    "Team e amministrazione",
    "Trasformazione",
    "Indirizzo e-mail",
    "Password",
    "Nome completo",
    "Conferma password",
    "Crea account",
    "Accedi",
    "Bentornato.",
  ],
  bn: [
    "প্রকল্প",
    "নতুন প্রকল্প",
    "অনুসন্ধান",
    "নথি",
    "বিশ্লেষণ",
    "সমাধান",
    "সমালোচনামূলক পর্যালোচনা",
    "পরিকল্পনা",
    "ডেলিভারেবল",
    "দল ও প্রশাসন",
    "রূপান্তর",
    "ইমেইল ঠিকানা",
    "পাসওয়ার্ড",
    "পুরো নাম",
    "পাসওয়ার্ড নিশ্চিত করুন",
    "অ্যাকাউন্ট তৈরি করুন",
    "সাইন ইন",
    "আবার স্বাগতম।",
  ],
  ta: [
    "திட்டங்கள்",
    "புதிய திட்டம்",
    "தேவைகள் ஆய்வு",
    "ஆவணங்கள்",
    "பகுப்பாய்வு",
    "தீர்வு",
    "விமர்சன ஆய்வு",
    "வரைவு",
    "வழங்கல்கள்",
    "குழுக்கள் மற்றும் நிர்வாகம்",
    "மாற்றம்",
    "மின்னஞ்சல்",
    "கடவுச்சொல்",
    "முழுப் பெயர்",
    "கடவுச்சொல்லை உறுதிப்படுத்து",
    "கணக்கு உருவாக்கு",
    "உள்நுழை",
    "மீண்டும் வருக.",
  ],
  te: [
    "ప్రాజెక్టులు",
    "కొత్త ప్రాజెక్ట్",
    "అన్వేషణ",
    "పత్రాలు",
    "విశ్లేషణ",
    "పరిష్కారం",
    "విమర్శనాత్మక సమీక్ష",
    "ప్రణాళిక",
    "ఫలితాలు",
    "బృందాలు మరియు నిర్వహణ",
    "పరివర్తన",
    "ఇమెయిల్ చిరునామా",
    "పాస్‌వర్డ్",
    "పూర్తి పేరు",
    "పాస్‌వర్డ్ నిర్ధారించండి",
    "ఖాతా సృష్టించండి",
    "సైన్ ఇన్",
    "తిరిగి స్వాగతం.",
  ],
  mr: [
    "प्रकल्प",
    "नवीन प्रकल्प",
    "शोध",
    "कागदपत्रे",
    "विश्लेषण",
    "उपाय",
    "चिकित्सक परीक्षण",
    "आराखडा",
    "निष्पत्ती",
    "संघ आणि प्रशासन",
    "परिवर्तन",
    "ईमेल पत्ता",
    "पासवर्ड",
    "पूर्ण नाव",
    "पासवर्डची पुष्टी",
    "खाते तयार करा",
    "साइन इन",
    "पुन्हा स्वागत आहे.",
  ],
  ur: [
    "منصوبے",
    "نیا منصوبہ",
    "دریافت",
    "دستاویزات",
    "تجزیہ",
    "حل",
    "تنقیدی جائزہ",
    "خاکہ",
    "نتائج",
    "ٹیمیں اور انتظامیہ",
    "تبدیلی",
    "ای میل پتہ",
    "پاس ورڈ",
    "پورا نام",
    "پاس ورڈ کی تصدیق",
    "اکاؤنٹ بنائیں",
    "سائن ان",
    "واپسی پر خوش آمدید۔",
  ],
  ru: [
    "Проекты",
    "Новый проект",
    "Исследование",
    "Документы",
    "Анализ",
    "Решение",
    "Критическая проверка",
    "План",
    "Результаты",
    "Команды и управление",
    "Трансформация",
    "Электронная почта",
    "Пароль",
    "Полное имя",
    "Подтвердите пароль",
    "Создать аккаунт",
    "Войти",
    "С возвращением.",
  ],
  id: [
    "Proyek",
    "Proyek baru",
    "Penemuan",
    "Dokumen",
    "Analisis",
    "Solusi",
    "Tinjauan kritis",
    "Cetak biru",
    "Hasil kerja",
    "Tim dan administrasi",
    "Transformasi",
    "Alamat email",
    "Kata sandi",
    "Nama lengkap",
    "Konfirmasi kata sandi",
    "Buat akun",
    "Masuk",
    "Selamat datang kembali.",
  ],
  tr: [
    "Projeler",
    "Yeni proje",
    "Keşif",
    "Belgeler",
    "Analiz",
    "Çözüm",
    "Eleştirel inceleme",
    "Plan",
    "Çıktılar",
    "Ekipler ve yönetim",
    "Dönüşüm",
    "E-posta adresi",
    "Parola",
    "Ad soyad",
    "Parolayı doğrula",
    "Hesap oluştur",
    "Giriş yap",
    "Tekrar hoş geldiniz.",
  ],
  vi: [
    "Dự án",
    "Dự án mới",
    "Khám phá",
    "Tài liệu",
    "Phân tích",
    "Giải pháp",
    "Đánh giá phản biện",
    "Bản thiết kế",
    "Sản phẩm bàn giao",
    "Nhóm và quản trị",
    "Chuyển đổi",
    "Địa chỉ email",
    "Mật khẩu",
    "Họ và tên",
    "Xác nhận mật khẩu",
    "Tạo tài khoản",
    "Đăng nhập",
    "Chào mừng trở lại.",
  ],
};
type Locale = {
  language: string;
  setLanguage: (v: string) => void;
  t: (v: string) => string;
  register: (v: string) => void;
  translate: () => Promise<void>;
  busy: boolean;
  error: string;
};
const Context = createContext<Locale>({
  language: "en",
  setLanguage: () => {},
  t: (v) => v,
  register: () => {},
  translate: async () => {},
  busy: false,
  error: "",
});
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState("en"),
    [dictionary, setDictionary] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const labels = useRef(new Set<string>());
  useEffect(() => {
    const stored = localStorage.getItem("shift-language");
    if (stored && languages[stored]) setLanguage(stored);
  }, []);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = ["ar", "ur"].includes(language)
      ? "rtl"
      : "ltr";
    localStorage.setItem("shift-language", language);
    try {
      setDictionary(
        JSON.parse(localStorage.getItem("shift-ui-" + language) || "{}"),
      );
    } catch {
      setDictionary({});
    }
  }, [language]);
  const register = useCallback((v: string) => {
    labels.current.add(v);
  }, []);
  const t = useCallback(
    (v: string) =>
      dictionary[v] || rows[language]?.[keys.indexOf(v.trim())] || v,
    [language, dictionary],
  );
  const translate = async () => {
    setBusy(true);
    setError("");
    try {
      const missing = Array.from(labels.current).filter(
        (v) => !dictionary[v] && !rows[language]?.[keys.indexOf(v.trim())],
      );
      let next = { ...dictionary };
      for (let i = 0; i < missing.length; i += 30) {
        const translated = await post<Record<string, string>>(
          `/localization/${language}`,
          { texts: missing.slice(i, i + 30) },
        );
        next = { ...next, ...translated };
        setDictionary(next);
        localStorage.setItem("shift-ui-" + language, JSON.stringify(next));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Context.Provider
      value={{ language, setLanguage, t, register, translate, busy, error }}
    >
      {children}
    </Context.Provider>
  );
}
export const useLocale = () => useContext(Context);
export function T({ text }: { text: string }) {
  const { t, register } = useLocale();
  useEffect(() => {
    if (knownLabels.has(text)) register(text);
  }, [text, register]);
  return <>{knownLabels.has(text) ? t(text) : text}</>;
}
export function LanguagePicker() {
  const { language, setLanguage, translate, busy, error } = useLocale();
  return (
    <div className="no-print">
      <select
        className="locale-picker"
        aria-label="Interface language"
        value={language}
        disabled={busy}
        onChange={(e) => setLanguage(e.target.value)}
      >
        {Object.entries(languages).map(([k, v]) => (
          <option value={k} key={k}>
            {v}
          </option>
        ))}
      </select>
      {language !== "en" && (
        <button
          className="text-button"
          disabled={busy}
          onClick={() => void translate()}
        >
          {busy ? "Translating…" : "Translate this page"}
        </button>
      )}
      {error && (
        <small role="alert">
          Translation unavailable; original text is shown.
        </small>
      )}
    </div>
  );
}
