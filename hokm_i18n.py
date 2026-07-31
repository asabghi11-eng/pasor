"""
Hokm internationalization — Phase 12 (زبان).

Five languages, matching the original phase-12 checklist:
فارسی (fa, default), انگلیسی (en), عربی (ar), ترکی (tr), روسی (ru).

Scope note (honest, like the other phase-12 modules): the existing
client (hokm-phase4-online.html + the panel .js files) is written with
hard-coded Persian strings in its markup — translating *all* of that
is a much bigger front-end refactor than one file can carry. What this
module actually delivers, end to end:

  - the language list + the player's chosen language, sent to the
    client as soon as they log in / reconnect (`i18n_state`), so a
    language switcher can be built against it;
  - a full string catalog per language for every user-facing message
    the *server* itself produces (errors, toasts, world-cup
    notifications) — those now come back in the player's language
    instead of being hard-coded Persian;
  - the same catalog also carries the labels used by the new phase-12
    UI (language/region/world-cup panel), so that panel is fully
    translated even though the rest of the client isn't yet.

Pure functions/data only (no I/O, no globals) — server.py owns
Player.language.
"""

DEFAULT_LANG = "fa"

LANGUAGES = [
    {"key": "fa", "native": "فارسی", "flag": "🇮🇷"},
    {"key": "en", "native": "English", "flag": "🇬🇧"},
    {"key": "ar", "native": "العربية", "flag": "🇸🇦"},
    {"key": "tr", "native": "Türkçe", "flag": "🇹🇷"},
    {"key": "ru", "native": "Русский", "flag": "🇷🇺"},
]

_VALID = {row["key"] for row in LANGUAGES}

# key -> {lang: string}. Keep every key present in every language;
# fall back to DEFAULT_LANG (and finally to the raw key) if one's ever
# missing at runtime.
_STRINGS = {
    # ---- server-side error/toast strings (used via I18N.t) -----------
    "room_code_invalid_or_full": {
        "fa": "کد اتاق نامعتبر است یا اتاق پر است",
        "en": "Room code is invalid or the room is full",
        "ar": "رمز الغرفة غير صالح أو الغرفة ممتلئة",
        "tr": "Oda kodu geçersiz ya da oda dolu",
        "ru": "Неверный код комнаты или комната заполнена",
    },
    "room_host_left": {
        "fa": "میزبان از اتاق خارج شد",
        "en": "The host left the room",
        "ar": "غادر المضيف الغرفة",
        "tr": "Oda sahibi odadan ayrıldı",
        "ru": "Хозяин покинул комнату",
    },
    "must_follow_suit": {
        "fa": "باید همرنگ بازی کنید",
        "en": "You must follow suit",
        "ar": "يجب اللعب بنفس لون الورقة",
        "tr": "Renge uymak zorundasın",
        "ru": "Нужно ходить в масть",
    },
    "room_not_found": {
        "fa": "اتاق پیدا نشد",
        "en": "Room not found",
        "ar": "لم يتم العثور على الغرفة",
        "tr": "Oda bulunamadı",
        "ru": "Комната не найдена",
    },
    "player_not_found": {
        "fa": "بازیکن پیدا نشد",
        "en": "Player not found",
        "ar": "لم يتم العثور على اللاعب",
        "tr": "Oyuncu bulunamadı",
        "ru": "Игрок не найден",
    },
    "already_in_clan": {
        "fa": "شما قبلاً عضو یک باشگاه هستید",
        "en": "You're already in a clan",
        "ar": "أنت بالفعل عضو في ناد",
        "tr": "Zaten bir kulüpte üyesin",
        "ru": "Вы уже состоите в клане",
    },
    "leave_clan_first": {
        "fa": "ابتدا از باشگاه فعلی خارج شوید",
        "en": "Leave your current clan first",
        "ar": "غادر ناديك الحالي أولاً",
        "tr": "Önce mevcut kulübünden ayrıl",
        "ru": "Сначала покиньте текущий клан",
    },
    "clan_code_not_found": {
        "fa": "کد باشگاه پیدا نشد",
        "en": "Clan code not found",
        "ar": "رمز النادي غير موجود",
        "tr": "Kulüp kodu bulunamadı",
        "ru": "Код клана не найден",
    },
    "clan_full": {
        "fa": "باشگاه پر است",
        "en": "The clan is full",
        "ar": "النادي ممتلئ",
        "tr": "Kulüp dolu",
        "ru": "Клан заполнен",
    },
    "not_in_any_clan": {
        "fa": "شما عضو هیچ باشگاهی نیستید",
        "en": "You're not in a clan",
        "ar": "أنت لست عضواً في أي ناد",
        "tr": "Herhangi bir kulüpte değilsin",
        "ru": "Вы не состоите в клане",
    },
    "gift_friends_only": {
        "fa": "فقط می‌توانید به دوستان هدیه بدهید",
        "en": "You can only gift friends",
        "ar": "يمكنك إهداء الأصدقاء فقط",
        "tr": "Sadece arkadaşlarına hediye verebilirsin",
        "ru": "Дарить подарки можно только друзьям",
    },
    "player_offline": {
        "fa": "بازیکن آفلاین است",
        "en": "Player is offline",
        "ar": "اللاعب غير متصل",
        "tr": "Oyuncu çevrimdışı",
        "ru": "Игрок не в сети",
    },
    "tournament_not_open": {
        "fa": "ثبت‌نام این تورنمنت باز نیست",
        "en": "Tournament registration is closed",
        "ar": "التسجيل في هذه البطولة مغلق",
        "tr": "Turnuva kaydı kapalı",
        "ru": "Регистрация на турнир закрыта",
    },
    "already_in_tournament": {
        "fa": "شما قبلاً در یک تورنمنت ثبت‌نام کرده‌اید",
        "en": "You're already registered in a tournament",
        "ar": "أنت مسجل بالفعل في بطولة",
        "tr": "Zaten bir turnuvaya kayıtlısın",
        "ru": "Вы уже зарегистрированы на турнир",
    },
    "tournament_full": {
        "fa": "ظرفیت تورنمنت تکمیل شده است",
        "en": "The tournament is full",
        "ar": "البطولة مكتملة العدد",
        "tr": "Turnuva kontenjanı dolu",
        "ru": "Турнир заполнен",
    },
    "region_invalid": {
        "fa": "منطقه انتخاب‌شده نامعتبر است",
        "en": "Invalid region",
        "ar": "المنطقة المحددة غير صالحة",
        "tr": "Geçersiz bölge",
        "ru": "Недопустимый регион",
    },
    "worldcup_not_eligible": {
        "fa": "برای ثبت‌نام در جام جهانی باید رتبه طلایی یا بالاتر داشته باشید",
        "en": "You need Gold rank or higher to join the World Cup",
        "ar": "تحتاج إلى رتبة ذهبية أو أعلى للانضمام إلى كأس العالم",
        "tr": "Dünya Kupası'na katılmak için Altın veya üstü rütbe gerekir",
        "ru": "Для участия в Кубке мира нужен ранг Золото или выше",
    },
    "worldcup_not_registration": {
        "fa": "ثبت‌نام جام جهانی این فصل بسته شده است",
        "en": "World Cup registration is closed for this season",
        "ar": "التسجيل في كأس العالم لهذا الموسم مغلق",
        "tr": "Bu sezon için Dünya Kupası kaydı kapalı",
        "ru": "Регистрация на Кубок мира в этом сезоне закрыта",
    },
    "worldcup_already_joined": {
        "fa": "شما قبلاً در جام جهانی این فصل ثبت‌نام کرده‌اید",
        "en": "You've already joined this season's World Cup",
        "ar": "لقد انضممت بالفعل إلى كأس العالم لهذا الموسم",
        "tr": "Bu sezonun Dünya Kupası'na zaten katıldın",
        "ru": "Вы уже присоединились к Кубку мира этого сезона",
    },
    "worldcup_eliminated": {
        "fa": "متأسفانه از جام جهانی حذف شدید",
        "en": "You've been eliminated from the World Cup",
        "ar": "للأسف تم إقصاؤك من كأس العالم",
        "tr": "Maalesef Dünya Kupası'ndan elendin",
        "ru": "К сожалению, вы выбыли из Кубка мира",
    },
    "too_many_reconnect_fails": {
        "fa": "تلاش‌های اتصال مجدد ناموفق زیاد بود، دوباره وارد شوید",
        "en": "Too many failed reconnect attempts — please log in again",
        "ar": "محاولات إعادة الاتصال الفاشلة كثيرة جداً — يرجى تسجيل الدخول مجدداً",
        "tr": "Çok fazla başarısız yeniden bağlanma denemesi — lütfen tekrar giriş yap",
        "ru": "Слишком много неудачных попыток переподключения — войдите заново",
    },
    "session_not_found": {
        "fa": "نشست پیدا نشد",
        "en": "Session not found",
        "ar": "لم يتم العثور على الجلسة",
        "tr": "Oturum bulunamadı",
        "ru": "Сессия не найдена",
    },
    "session_expired": {
        "fa": "نشست شما منقضی شده، دوباره وارد شوید",
        "en": "Your session has expired — please log in again",
        "ar": "انتهت صلاحية جلستك — يرجى تسجيل الدخول مجدداً",
        "tr": "Oturumun süresi doldu — lütfen tekrar giriş yap",
        "ru": "Ваша сессия истекла — войдите заново",
    },
    "must_login_first": {
        "fa": "ابتدا باید وارد شوید",
        "en": "You must log in first",
        "ar": "يجب تسجيل الدخول أولاً",
        "tr": "Önce giriş yapmalısın",
        "ru": "Сначала нужно войти",
    },
    "google_login_not_configured": {
        "fa": "ورود با گوگل روی این سرور هنوز تنظیم نشده",
        "en": "Google login isn't configured on this server yet",
        "ar": "تسجيل الدخول بجوجل غير مُعد على هذا الخادم بعد",
        "tr": "Google ile giriş bu sunucuda henüz ayarlanmadı",
        "ru": "Вход через Google ещё не настроен на этом сервере",
    },
    "google_login_failed": {
        "fa": "ورود با گوگل ناموفق بود، دوباره تلاش کن",
        "en": "Google login failed — please try again",
        "ar": "فشل تسجيل الدخول بجوجل — حاول مرة أخرى",
        "tr": "Google ile giriş başarısız — tekrar dene",
        "ru": "Не удалось войти через Google — попробуйте снова",
    },
    "must_use_real_payment": {
        "fa": "این خرید باید از درگاه پرداخت واقعی انجام شود",
        "en": "This purchase must go through the real payment gateway",
        "ar": "يجب إتمام هذا الشراء عبر بوابة الدفع الحقيقية",
        "tr": "Bu satın alma gerçek ödeme ağ geçidinden yapılmalı",
        "ru": "Эту покупку нужно совершить через настоящий платёжный шлюз",
    },
    "payment_item_not_found": {
        "fa": "آیتم موردنظر پیدا نشد",
        "en": "Item not found",
        "ar": "العنصر غير موجود",
        "tr": "Öğe bulunamadı",
        "ru": "Товар не найден",
    },

    # ---- phase-12 panel UI labels (language / region / world cup) ----
    "panel_title": {
        "fa": "زبان، منطقه و جام جهانی",
        "en": "Language, Region & World Cup",
        "ar": "اللغة والمنطقة وكأس العالم",
        "tr": "Dil, Bölge ve Dünya Kupası",
        "ru": "Язык, регион и Кубок мира",
    },
    "tab_language": {
        "fa": "زبان", "en": "Language", "ar": "اللغة", "tr": "Dil", "ru": "Язык",
    },
    "tab_region": {
        "fa": "منطقه", "en": "Region", "ar": "المنطقة", "tr": "Bölge", "ru": "Регион",
    },
    "tab_worldcup": {
        "fa": "جام جهانی", "en": "World Cup", "ar": "كأس العالم", "tr": "Dünya Kupası", "ru": "Кубок мира",
    },
    "region_leaderboard": {
        "fa": "جدول امتیازات منطقه‌ای",
        "en": "Regional leaderboard",
        "ar": "لوحة الصدارة الإقليمية",
        "tr": "Bölgesel lider tablosu",
        "ru": "Региональная таблица лидеров",
    },
    "worldcup_join": {
        "fa": "ثبت‌نام در جام جهانی",
        "en": "Join the World Cup",
        "ar": "انضم إلى كأس العالم",
        "tr": "Dünya Kupası'na katıl",
        "ru": "Присоединиться к Кубку мира",
    },
    "worldcup_status_registration": {
        "fa": "ثبت‌نام باز است",
        "en": "Registration open",
        "ar": "التسجيل مفتوح",
        "tr": "Kayıt açık",
        "ru": "Регистрация открыта",
    },
    "worldcup_status_qualifiers": {
        "fa": "مرحله مقدماتی",
        "en": "Qualifiers",
        "ar": "الدور التمهيدي",
        "tr": "Eleme turları",
        "ru": "Отборочный этап",
    },
    "worldcup_status_finals": {
        "fa": "مرحله نهایی",
        "en": "Finals",
        "ar": "النهائيات",
        "tr": "Finaller",
        "ru": "Финал",
    },
    "worldcup_status_finished": {
        "fa": "پایان‌یافته",
        "en": "Finished",
        "ar": "انتهت",
        "tr": "Bitti",
        "ru": "Завершён",
    },
    "worldcup_champion": {
        "fa": "قهرمان فصل",
        "en": "Season champion",
        "ar": "بطل الموسم",
        "tr": "Sezon şampiyonu",
        "ru": "Чемпион сезона",
    },

    # ---- client UI strings (login / lobby / matchmaking / room / settings) --
    # Consumed by hokm-phase4-online.html via t(key, fallback); fallback is
    # always the original Persian string, so a catalog miss (or an old
    # cached client) degrades to exactly today's behavior.
    "login_subtitle": {
        "fa": "پاسور ایرانی — آنلاین با دوستان",
        "en": "Iranian Pasur — online with friends",
        "ar": "الباسور الإيراني — عبر الإنترنت مع الأصدقاء",
        "tr": "İran Pasuru — arkadaşlarla çevrimiçi",
        "ru": "Иранский Пасур — онлайн с друзьями",
    },
    "login_with_google": {
        "fa": "ورود با گوگل", "en": "Sign in with Google", "ar": "تسجيل الدخول عبر جوجل",
        "tr": "Google ile giriş yap", "ru": "Войти через Google",
    },
    "or_divider": {
        "fa": "یا", "en": "or", "ar": "أو", "tr": "veya", "ru": "или",
    },
    "continue_as_guest": {
        "fa": "ادامه به‌عنوان مهمان", "en": "Continue as guest", "ar": "المتابعة كضيف",
        "tr": "Misafir olarak devam et", "ru": "Продолжить как гость",
    },
    "connecting": {
        "fa": "در حال اتصال...", "en": "Connecting...", "ar": "جارٍ الاتصال...",
        "tr": "Bağlanıyor...", "ru": "Подключение...",
    },
    "login_server_note": {
        "fa": "برای بازی آنلاین باید سرور (server.py) روشن باشه. آدرس اتصال: {url}",
        "en": "The server (server.py) must be running for online play. Server address: {url}",
        "ar": "يجب أن يعمل الخادم (server.py) للعب عبر الإنترنت. عنوان الخادم: {url}",
        "tr": "Çevrimiçi oynamak için sunucu (server.py) çalışıyor olmalı. Sunucu adresi: {url}",
        "ru": "Для онлайн-игры сервер (server.py) должен быть запущен. Адрес сервера: {url}",
    },
    "default_player_name": {
        "fa": "بازیکن", "en": "Player", "ar": "لاعب", "tr": "Oyuncu", "ru": "Игрок",
    },
    "settings_tooltip": {
        "fa": "تنظیمات", "en": "Settings", "ar": "الإعدادات", "tr": "Ayarlar", "ru": "Настройки",
    },
    "quick_match_title": {
        "fa": "بازی سریع", "en": "Quick match", "ar": "مباراة سريعة", "tr": "Hızlı eşleşme", "ru": "Быстрая игра",
    },
    "quick_match_desc": {
        "fa": "متچ‌میکینگ خودکار با بازیکن دیگه",
        "en": "Automatic matchmaking with another player",
        "ar": "مطابقة تلقائية مع لاعب آخر",
        "tr": "Başka bir oyuncuyla otomatik eşleşme",
        "ru": "Автоматический подбор соперника",
    },
    "create_room_title": {
        "fa": "ساخت اتاق خصوصی", "en": "Create a private room", "ar": "إنشاء غرفة خاصة",
        "tr": "Özel oda oluştur", "ru": "Создать приватную комнату",
    },
    "create_room_desc": {
        "fa": "یه کد بساز و برای دوستات بفرست",
        "en": "Create a code and send it to your friends",
        "ar": "أنشئ رمزًا وأرسله لأصدقائك",
        "tr": "Bir kod oluştur ve arkadaşlarına gönder",
        "ru": "Создайте код и отправьте друзьям",
    },
    "join_with_code": {
        "fa": "پیوستن با کد", "en": "Join with a code", "ar": "الانضمام برمز",
        "tr": "Kod ile katıl", "ru": "Присоединиться по коду",
    },
    "join_btn": {
        "fa": "ورود", "en": "Join", "ar": "انضمام", "tr": "Katıl", "ru": "Войти",
    },
    "lobby_note": {
        "fa": "اینا الان روی سرور واقعی WebSocket کار می‌کنن. برای تست reconnect، وسط بازی از تنظیمات (⚙) اتصال رو قطع کن.",
        "en": "This now runs on a real WebSocket server. To test reconnect, disconnect mid-game from settings (⚙).",
        "ar": "هذا يعمل الآن على خادم WebSocket حقيقي. لاختبار إعادة الاتصال، اقطع الاتصال أثناء اللعب من الإعدادات (⚙).",
        "tr": "Bu artık gerçek bir WebSocket sunucusunda çalışıyor. Yeniden bağlanmayı test etmek için oyun ortasında ayarlardan (⚙) bağlantıyı kes.",
        "ru": "Теперь это работает на настоящем WebSocket-сервере. Чтобы проверить переподключение, разорвите соединение в настройках (⚙) во время игры.",
    },
    "finding_opponent": {
        "fa": "در حال پیدا کردن حریف...", "en": "Finding an opponent...", "ar": "جارٍ البحث عن خصم...",
        "tr": "Rakip aranıyor...", "ru": "Поиск соперника...",
    },
    "rank_label": {
        "fa": "رتبه", "en": "Rank", "ar": "الرتبة", "tr": "Rütbe", "ru": "Ранг",
    },
    "time_label": {
        "fa": "زمان", "en": "Time", "ar": "الوقت", "tr": "Süre", "ru": "Время",
    },
    "ping_label": {
        "fa": "پینگ", "en": "Ping", "ar": "زمن الاستجابة", "tr": "Ping", "ru": "Пинг",
    },
    "cancel_btn": {
        "fa": "لغو", "en": "Cancel", "ar": "إلغاء", "tr": "İptal", "ru": "Отмена",
    },
    "private_room_title": {
        "fa": "اتاق خصوصی", "en": "Private room", "ar": "غرفة خاصة", "tr": "Özel oda", "ru": "Приватная комната",
    },
    "seat_south_host": {
        "fa": "جنوب (میزبان)", "en": "South (host)", "ar": "الجنوب (المضيف)",
        "tr": "Güney (kurucu)", "ru": "Юг (хост)",
    },
    "seat_north": {
        "fa": "شمال", "en": "North", "ar": "الشمال", "tr": "Kuzey", "ru": "Север",
    },
    "seat_east": {
        "fa": "شرق", "en": "East", "ar": "الشرق", "tr": "Doğu", "ru": "Восток",
    },
    "seat_west": {
        "fa": "غرب", "en": "West", "ar": "الغرب", "tr": "Batı", "ru": "Запад",
    },
    "you_suffix": {
        "fa": "(شما)", "en": "(you)", "ar": "(أنت)", "tr": "(siz)", "ru": "(вы)",
    },
    "waiting_join": {
        "fa": "در انتظار پیوستن...", "en": "Waiting for a player...", "ar": "في انتظار الانضمام...",
        "tr": "Katılım bekleniyor...", "ru": "Ожидание игрока...",
    },
    "start_with_bots_btn": {
        "fa": "شروع بازی با ربات برای صندلی‌های خالی",
        "en": "Start with bots for the empty seats",
        "ar": "ابدأ باستخدام بوتات للمقاعد الفارغة",
        "tr": "Boş koltuklar için botlarla başla",
        "ru": "Начать с ботами на пустых местах",
    },
    "leave_room_btn": {
        "fa": "خروج از اتاق", "en": "Leave room", "ar": "مغادرة الغرفة", "tr": "Odadan çık", "ru": "Покинуть комнату",
    },
    "room_wait_note": {
        "fa": "این کد رو برای تا ۳ نفر از دوستات بفرست؛ هر کدوم توی «پیوستن با کد» همین کد رو وارد کنن (همه باید به همین سرور وصل باشید). با پر شدن هر ۴ صندلی بازی خودکار شروع می‌شه، یا می‌تونی زودتر با ربات برای بقیه صندلی‌ها شروع کنی.",
        "en": "Send this code to up to 3 friends; each of them enters it under \"Join with a code\" (everyone must connect to the same server). The game starts automatically once all 4 seats are filled, or you can start earlier with bots filling the rest.",
        "ar": "أرسل هذا الرمز إلى ما يصل إلى 3 أصدقاء؛ يقوم كل منهم بإدخاله في \"الانضمام برمز\" (يجب أن يتصل الجميع بنفس الخادم). تبدأ اللعبة تلقائيًا عند امتلاء جميع المقاعد الأربعة، أو يمكنك البدء مبكرًا باستخدام بوتات للمقاعد المتبقية.",
        "tr": "Bu kodu en fazla 3 arkadaşınla paylaş; her biri \"Kod ile katıl\" kısmına aynı kodu girsin (herkes aynı sunucuya bağlı olmalı). 4 koltuk da dolunca oyun otomatik başlar, ya da kalan koltuklar için botlarla daha erken başlayabilirsin.",
        "ru": "Отправьте этот код до 3 друзей; каждый вводит его в разделе «Присоединиться по коду» (все должны быть подключены к одному серверу). Игра начнётся автоматически, когда заполнятся все 4 места, либо можно начать раньше с ботами на оставшихся местах.",
    },
    "settings_title": {
        "fa": "پروفایل و شخصی‌سازی", "en": "Profile & personalization", "ar": "الملف الشخصي والتخصيص",
        "tr": "Profil ve kişiselleştirme", "ru": "Профиль и персонализация",
    },
    "tab_profile": {
        "fa": "پروفایل", "en": "Profile", "ar": "الملف الشخصي", "tr": "Profil", "ru": "Профиль",
    },
    "tab_theme": {
        "fa": "پوسته و میز", "en": "Skin & table", "ar": "المظهر والطاولة", "tr": "Görünüm ve masa", "ru": "Тема и стол",
    },
    "close_btn": {
        "fa": "بستن", "en": "Close", "ar": "إغلاق", "tr": "Kapat", "ru": "Закрыть",
    },
    "avatar_label": {
        "fa": "آواتار", "en": "Avatar", "ar": "الصورة الرمزية", "tr": "Avatar", "ru": "Аватар",
    },
    "frame_label": {
        "fa": "قاب پروفایل", "en": "Profile frame", "ar": "إطار الملف الشخصي", "tr": "Profil çerçevesi", "ru": "Рамка профиля",
    },
    "background_label": {
        "fa": "بک‌گراند", "en": "Background", "ar": "الخلفية", "tr": "Arka plan", "ru": "Фон",
    },
    "network_test_label": {
        "fa": "تست شبکه", "en": "Network test", "ar": "اختبار الشبكة", "tr": "Ağ testi", "ru": "Проверка сети",
    },
    "disconnect_test_btn": {
        "fa": "قطع واقعی اتصال (تست reconnect)",
        "en": "Really disconnect (test reconnect)",
        "ar": "قطع الاتصال فعليًا (اختبار إعادة الاتصال)",
        "tr": "Bağlantıyı gerçekten kes (yeniden bağlanmayı test et)",
        "ru": "Реально разорвать соединение (тест переподключения)",
    },
    "name_placeholder": {
        "fa": "اسمت رو بنویس", "en": "Enter your name", "ar": "اكتب اسمك", "tr": "Adını yaz", "ru": "Введите имя",
    },

    # ---- in-game screen (topbar / overlays / footnote / suit names) --------
    "topbar_subtitle": {
        "fa": "فاز ۴ — آنلاین (سرور واقعی)", "en": "Phase 4 — Online (real server)",
        "ar": "المرحلة 4 — عبر الإنترنت (خادم حقيقي)", "tr": "Faz 4 — Çevrimiçi (gerçek sunucu)",
        "ru": "Фаза 4 — Онлайн (реальный сервер)",
    },
    "your_team": {
        "fa": "تیم شما", "en": "Your team", "ar": "فريقك", "tr": "Takımınız", "ru": "Ваша команда",
    },
    "opponent": {
        "fa": "حریف", "en": "Opponent", "ar": "الخصم", "tr": "Rakip", "ru": "Соперник",
    },
    "reconnect_banner": {
        "fa": "📡 اتصال قطع شد — در حال تلاش برای اتصال مجدد...",
        "en": "📡 Connection lost — trying to reconnect...",
        "ar": "📡 انقطع الاتصال — جارٍ محاولة إعادة الاتصال...",
        "tr": "📡 Bağlantı koptu — yeniden bağlanmaya çalışılıyor...",
        "ru": "📡 Соединение потеряно — попытка переподключения...",
    },
    "preparing_title": {
        "fa": "در حال آماده‌سازی بازی...", "en": "Preparing the game...", "ar": "جارٍ تجهيز اللعبة...",
        "tr": "Oyun hazırlanıyor...", "ru": "Подготовка игры...",
    },
    "preparing_desc": {
        "fa": "چند لحظه صبر کن تا کارت‌ها پخش بشه.", "en": "Hang on while the cards are dealt.",
        "ar": "انتظر قليلاً حتى يتم توزيع الأوراق.", "tr": "Kartlar dağıtılırken bir dakika bekle.",
        "ru": "Подождите, пока раздаются карты.",
    },
    "hakem_title": {
        "fa": "شما حاکم هستید!", "en": "You are the hakem!", "ar": "أنت الحاكم!",
        "tr": "Sen hakemsin!", "ru": "Вы — хаким!",
    },
    "hakem_desc": {
        "fa": "یکی از این ۵ کارت رو دارید. یک خال رو به عنوان «حکم» انتخاب کنید:",
        "en": "You hold these 5 cards. Choose one suit as trump (\"hokm\"):",
        "ar": "لديك هذه الأوراق الخمس. اختر إحدى المجموعات كورقة رابحة (\"حكم\"):",
        "tr": "Bu 5 kartı elinde tutuyorsun. Bir rengi koz (\"hükm\") olarak seç:",
        "ru": "У вас эти 5 карт. Выберите одну масть в качестве козыря («хокм»):",
    },
    "choosing_trump_title": {
        "fa": "انتخاب حکم", "en": "Choosing trump", "ar": "اختيار الورقة الرابحة",
        "tr": "Koz seçimi", "ru": "Выбор козыря",
    },
    "choosing_trump_desc": {
        "fa": "{name} حاکم این دست است و در حال انتخاب خال حکم است...",
        "en": "{name} is the hakem this hand and is choosing the trump suit...",
        "ar": "{name} هو الحاكم في هذه الجولة ويقوم باختيار الورقة الرابحة...",
        "tr": "{name} bu elde hakem ve koz rengini seçiyor...",
        "ru": "{name} — хаким в этой раздаче и сейчас выбирает козырь...",
    },
    "hand_won_title": {
        "fa": "دست به تیم شما رسید! 🎉", "en": "Your team won the hand! 🎉",
        "ar": "فاز فريقك بالجولة! 🎉", "tr": "Eli takımınız kazandı! 🎉", "ru": "Ваша команда выиграла раздачу! 🎉",
    },
    "hand_lost_title": {
        "fa": "این دست رو حریف برد", "en": "The opponent won this hand",
        "ar": "فاز الخصم بهذه الجولة", "tr": "Bu eli rakip kazandı", "ru": "Эту раздачу выиграл соперник",
    },
    "hand_result_line": {
        "fa": "نتیجه‌ی این دست: {a} - {b} (تیک)",
        "en": "Result of this hand: {a} - {b} (tricks)",
        "ar": "نتيجة هذه الجولة: {a} - {b} (خدع)",
        "tr": "Bu elin sonucu: {a} - {b} (el sayısı)",
        "ru": "Результат раздачи: {a} - {b} (взятки)",
    },
    "match_score_line": {
        "fa": "امتیاز مسابقه: تیم شما {a} — حریف {b}",
        "en": "Match score: your team {a} — opponent {b}",
        "ar": "نتيجة المباراة: فريقك {a} — الخصم {b}",
        "tr": "Maç skoru: takımınız {a} — rakip {b}",
        "ru": "Счёт матча: ваша команда {a} — соперник {b}",
    },
    "next_hand_btn": {
        "fa": "دست بعدی", "en": "Next hand", "ar": "الجولة التالية", "tr": "Sonraki el", "ru": "Следующая раздача",
    },
    "match_won_title": {
        "fa": "برنده شدید! 🏆", "en": "You won! 🏆", "ar": "لقد فزت! 🏆", "tr": "Kazandın! 🏆", "ru": "Вы победили! 🏆",
    },
    "match_lost_title": {
        "fa": "مسابقه رو باختید", "en": "You lost the match", "ar": "خسرت المباراة",
        "tr": "Maçı kaybettin", "ru": "Вы проиграли матч",
    },
    "final_result_line": {
        "fa": "نتیجه‌ی نهایی: تیم شما {a} دست — حریف {b} دست",
        "en": "Final result: your team {a} hands — opponent {b} hands",
        "ar": "النتيجة النهائية: فريقك {a} جولة — الخصم {b} جولة",
        "tr": "Sonuç: takımınız {a} el — rakip {b} el",
        "ru": "Итог: ваша команда {a} раздач — соперник {b} раздач",
    },
    "new_match_btn": {
        "fa": "مسابقه‌ی جدید", "en": "New match", "ar": "مباراة جديدة", "tr": "Yeni maç", "ru": "Новый матч",
    },
    "footnote_tricks": {
        "fa": "تیک‌های این دست — تیم شما: {a} \u00a0|\u00a0 حریف: {b}",
        "en": "Tricks this hand — your team: {a} \u00a0|\u00a0 opponent: {b}",
        "ar": "خدع هذه الجولة — فريقك: {a} \u00a0|\u00a0 الخصم: {b}",
        "tr": "Bu elin sayıları — takımınız: {a} \u00a0|\u00a0 rakip: {b}",
        "ru": "Взятки в этой раздаче — ваша команда: {a} \u00a0|\u00a0 соперник: {b}",
    },
    "footnote_note": {
        "fa": "فاز ۴: ورود مهمان، اتاق خصوصی و بازی سریع روی سرور واقعی با WebSocket، پینگ واقعی و reconnect خودکار. سیستم رتبه‌بندی واقعی و اقتصاد بازی در فازهای بعدی.",
        "en": "Phase 4: guest login, private rooms and quick match on a real WebSocket server, real ping and automatic reconnect. A real ranking system and in-game economy come in later phases.",
        "ar": "المرحلة 4: تسجيل دخول الضيف، الغرف الخاصة والمباراة السريعة على خادم WebSocket حقيقي، بينغ حقيقي وإعادة اتصال تلقائية. نظام تصنيف حقيقي واقتصاد داخل اللعبة في المراحل اللاحقة.",
        "tr": "Faz 4: misafir girişi, özel odalar ve gerçek bir WebSocket sunucusunda hızlı eşleşme, gerçek ping ve otomatik yeniden bağlanma. Gerçek sıralama sistemi ve oyun içi ekonomi sonraki fazlarda.",
        "ru": "Фаза 4: гостевой вход, приватные комнаты и быстрая игра на настоящем WebSocket-сервере, реальный пинг и автоматическое переподключение. Настоящая система рангов и внутриигровая экономика — в следующих фазах.",
    },
    "suit_spades": {
        "fa": "پیک", "en": "Spades", "ar": "البستوني", "tr": "Maça", "ru": "Пики",
    },
    "suit_hearts": {
        "fa": "دل", "en": "Hearts", "ar": "الكوبا", "tr": "Kupa", "ru": "Червы",
    },
    "suit_diamonds": {
        "fa": "خشت", "en": "Diamonds", "ar": "الديناري", "tr": "Karo", "ru": "Бубны",
    },
    "suit_clubs": {
        "fa": "گشنیز", "en": "Clubs", "ar": "السباتي", "tr": "Sinek", "ru": "Трефы",
    },

    # ---- panel UI strings (economy/social/tournament/worldcup/monetization/stats/achievements panels) ----
    "eco_tab_missions": {
        "fa": 'ماموریت\u200cها', "en": 'Missions', "ar": 'المهام', "tr": 'Görevler', "ru": 'Задания',
    },
    "eco_tab_shop": {
        "fa": 'فروشگاه', "en": 'Shop', "ar": 'المتجر', "tr": 'Mağaza', "ru": 'Магазин',
    },
    "eco_tab_wheel": {
        "fa": 'گردونه شانس', "en": 'Lucky wheel', "ar": 'عجلة الحظ', "tr": 'Şans çarkı', "ru": 'Колесо удачи',
    },
    "eco_tab_boxes": {
        "fa": 'جعبه\u200cها', "en": 'Boxes', "ar": 'الصناديق', "tr": 'Kutular', "ru": 'Сундуки',
    },
    "eco_title": {
        "fa": 'اقتصاد بازی', "en": 'Game economy', "ar": 'اقتصاد اللعبة', "tr": 'Oyun ekonomisi', "ru": 'Игровая экономика',
    },
    "eco_coins_label": {
        "fa": 'سکه', "en": 'coins', "ar": 'عملات', "tr": 'jeton', "ru": 'монет',
    },
    "eco_gems_label": {
        "fa": 'جم', "en": 'gems', "ar": 'جواهر', "tr": 'elmas', "ru": 'кристаллов',
    },
    "eco_level_label": {
        "fa": 'لول', "en": 'Level', "ar": 'المستوى', "tr": 'Seviye', "ru": 'Уровень',
    },
    "eco_xp_to_next": {
        "fa": '{xp} / {need} XP تا لول بعد', "en": '{xp} / {need} XP to next level', "ar": '{xp} / {need} XP للمستوى التالي', "tr": 'Sonraki seviyeye {xp} / {need} XP', "ru": '{xp} / {need} XP до след. уровня',
    },
    "eco_no_missions": {
        "fa": 'ماموریتی برای امروز نیست.', "en": 'No missions for today.', "ar": 'لا توجد مهام لهذا اليوم.', "tr": 'Bugün için görev yok.', "ru": 'На сегодня заданий нет.',
    },
    "eco_mission_claimed": {
        "fa": 'دریافت شد', "en": 'Claimed', "ar": 'تم الاستلام', "tr": 'Alındı', "ru": 'Получено',
    },
    "eco_mission_claim": {
        "fa": 'دریافت جایزه', "en": 'Claim reward', "ar": 'استلام الجائزة', "tr": 'Ödülü al', "ru": 'Забрать награду',
    },
    "eco_owned": {
        "fa": 'خریداری شده', "en": 'Owned', "ar": 'تم الشراء', "tr": 'Satın alındı', "ru": 'Куплено',
    },
    "eco_buy": {
        "fa": 'خرید', "en": 'Buy', "ar": 'شراء', "tr": 'Satın al', "ru": 'Купить',
    },
    "eco_spin_free": {
        "fa": 'بچرخون! (رایگان، یک بار در روز)', "en": 'Spin! (free, once a day)', "ar": 'أدر العجلة! (مجاناً، مرة يومياً)', "tr": 'Çevir! (ücretsiz, günde bir kez)', "ru": 'Крутить! (бесплатно, раз в день)',
    },
    "eco_spin_done": {
        "fa": 'امروز چرخوندی — فردا بیا', "en": 'Already spun today — come back tomorrow', "ar": 'أدرتها اليوم — عد غداً', "tr": 'Bugün çevirdin — yarın gel', "ru": 'Уже крутили сегодня — приходите завтра',
    },
    "eco_cant_spin": {
        "fa": 'نمیشه چرخوند', "en": "Can't spin right now", "ar": 'لا يمكن الإدارة الآن', "tr": 'Şu an çevrilemiyor', "ru": 'Сейчас нельзя крутить',
    },
    "eco_won_prize": {
        "fa": 'بردی: {label} 🎉', "en": 'You won: {label} 🎉', "ar": 'ربحت: {label} 🎉', "tr": 'Kazandın: {label} 🎉', "ru": 'Вы выиграли: {label} 🎉',
    },
    "eco_wheel_prize_toast": {
        "fa": 'جایزه گردونه: {label}', "en": 'Wheel prize: {label}', "ar": 'جائزة العجلة: {label}', "tr": 'Çark ödülü: {label}', "ru": 'Приз колеса: {label}',
    },
    "eco_box_bronze": {
        "fa": 'جعبه برنزی', "en": 'Bronze box', "ar": 'صندوق برونزي', "tr": 'Bronz kutu', "ru": 'Бронзовый сундук',
    },
    "eco_box_silver": {
        "fa": 'جعبه نقره\u200cای', "en": 'Silver box', "ar": 'صندوق فضي', "tr": 'Gümüş kutu', "ru": 'Серебряный сундук',
    },
    "eco_box_gold": {
        "fa": 'جعبه طلایی', "en": 'Gold box', "ar": 'صندوق ذهبي', "tr": 'Altın kutu', "ru": 'Золотой сундук',
    },
    "eco_match_reward": {
        "fa": 'پاداش بازی: {coins} سکه', "en": 'Match reward: {coins} coins', "ar": 'مكافأة المباراة: {coins} عملة', "tr": 'Maç ödülü: {coins} jeton', "ru": 'Награда за матч: {coins} монет',
    },
    "eco_gems_suffix": {
        "fa": '، {gems} جم', "en": ', {gems} gems', "ar": '، {gems} جوهرة', "tr": ', {gems} elmas', "ru": ', {gems} кристаллов',
    },
    "eco_leveled_up": {
        "fa": ' — لول\u200cآپ شدی! 🎉', "en": ' — you leveled up! 🎉', "ar": ' — لقد ارتقيت مستوى! 🎉', "tr": ' — seviye atladın! 🎉', "ru": ' — повышен уровень! 🎉',
    },
    "eco_claim_error": {
        "fa": 'خطا در دریافت جایزه', "en": 'Error claiming reward', "ar": 'خطأ في استلام الجائزة', "tr": 'Ödül alınırken hata', "ru": 'Ошибка получения награды',
    },
    "eco_bought": {
        "fa": 'خریداری شد: {name}', "en": 'Purchased: {name}', "ar": 'تم الشراء: {name}', "tr": 'Satın alındı: {name}', "ru": 'Куплено: {name}',
    },
    "eco_buy_error": {
        "fa": 'خطا در خرید', "en": 'Purchase error', "ar": 'خطأ في الشراء', "tr": 'Satın alma hatası', "ru": 'Ошибка покупки',
    },
    "eco_box_reward": {
        "fa": 'از جعبه گرفتی: {coins} سکه', "en": 'You got from the box: {coins} coins', "ar": 'حصلت من الصندوق على: {coins} عملة', "tr": 'Kutudan aldın: {coins} jeton', "ru": 'Из сундука получено: {coins} монет',
    },
    "eco_box_reward_gems": {
        "fa": ' + {gems} جم', "en": ' + {gems} gems', "ar": ' + {gems} جوهرة', "tr": ' + {gems} elmas', "ru": ' + {gems} кристаллов',
    },
    "eco_box_error": {
        "fa": 'خطا در باز کردن جعبه', "en": 'Error opening box', "ar": 'خطأ في فتح الصندوق', "tr": 'Kutu açma hatası', "ru": 'Ошибка открытия сундука',
    },
    "soc_qc_0": {
        "fa": 'دمت گرم!', "en": 'Nice one!', "ar": 'أحسنت!', "tr": 'Aferin!', "ru": 'Молодец!',
    },
    "soc_qc_1": {
        "fa": 'آفرین :)', "en": 'Well done :)', "ar": 'رائع :)', "tr": 'Bravo :)', "ru": 'Отлично :)',
    },
    "soc_qc_2": {
        "fa": 'بد شانسی!', "en": 'Bad luck!', "ar": 'سوء حظ!', "tr": 'Şanssızlık!', "ru": 'Не повезло!',
    },
    "soc_qc_3": {
        "fa": 'حکم خوبی بود', "en": 'Good trump call', "ar": 'اختيار جيد للورقة الرابحة', "tr": 'İyi koz seçimiydi', "ru": 'Хороший выбор козыря',
    },
    "soc_qc_4": {
        "fa": 'دوباره بازی می\u200cکنیم؟', "en": 'Play again?', "ar": 'هل نلعب مرة أخرى؟', "tr": 'Tekrar oynayalım mı?', "ru": 'Сыграем ещё?',
    },
    "soc_qc_5": {
        "fa": 'خیلی خوب بود!', "en": 'That was great!', "ar": 'كان ذلك رائعاً!', "tr": 'Çok iyiydi!', "ru": 'Это было здорово!',
    },
    "soc_friend_added": {
        "fa": '{name} به لیست دوستانت اضافه شد', "en": '{name} was added to your friends list', "ar": 'تمت إضافة {name} إلى قائمة أصدقائك', "tr": '{name} arkadaş listene eklendi', "ru": '{name} добавлен(а) в друзья',
    },
    "soc_gift_sent": {
        "fa": '{amount} سکه به {name} هدیه دادی', "en": 'You sent {amount} coins to {name}', "ar": 'أرسلت {amount} عملة إلى {name}', "tr": '{name} kişisine {amount} jeton hediye ettin', "ru": 'Вы отправили {amount} монет игроку {name}',
    },
    "soc_gift_received": {
        "fa": '{name} به تو {amount} سکه هدیه داد! 🎁', "en": '{name} sent you {amount} coins! 🎁', "ar": 'أرسل لك {name} {amount} عملة! 🎁', "tr": '{name} sana {amount} jeton hediye etti! 🎁', "ru": '{name} подарил(а) вам {amount} монет! 🎁',
    },
    "soc_muted": {
        "fa": 'چت تو موقتاً محدود شده', "en": 'Your chat is temporarily restricted', "ar": 'تم تقييد الدردشة الخاصة بك مؤقتاً', "tr": 'Sohbetin geçici olarak kısıtlandı', "ru": 'Ваш чат временно ограничен',
    },
    "soc_report_sent": {
        "fa": 'گزارش ثبت شد، ممنون از کمکت', "en": 'Report submitted, thanks for your help', "ar": 'تم إرسال البلاغ، شكراً لمساعدتك', "tr": 'Rapor gönderildi, yardımın için teşekkürler', "ru": 'Жалоба отправлена, спасибо за помощь',
    },
    "soc_fab_label": {
        "fa": 'چت و دوستان', "en": 'Chat & friends', "ar": 'الدردشة والأصدقاء', "tr": 'Sohbet ve arkadaşlar', "ru": 'Чат и друзья',
    },
    "soc_title": {
        "fa": 'اجتماعی', "en": 'Social', "ar": 'اجتماعي', "tr": 'Sosyal', "ru": 'Общение',
    },
    "soc_tab_chat": {
        "fa": 'چت', "en": 'Chat', "ar": 'الدردشة', "tr": 'Sohbet', "ru": 'Чат',
    },
    "soc_tab_friends": {
        "fa": 'دوستان', "en": 'Friends', "ar": 'الأصدقاء', "tr": 'Arkadaşlar', "ru": 'Друзья',
    },
    "soc_tab_clan": {
        "fa": 'باشگاه', "en": 'Clan', "ar": 'العشيرة', "tr": 'Klan', "ru": 'Клан',
    },
    "soc_tab_gift": {
        "fa": 'هدیه', "en": 'Gift', "ar": 'هدية', "tr": 'Hediye', "ru": 'Подарок',
    },
    "soc_chat_unavailable": {
        "fa": 'چت و ایموجی فقط داخل یک بازی فعال هستن — اول یک بازی شروع کن.', "en": 'Chat and emoji are only available inside an active game — start a game first.', "ar": 'الدردشة والرموز التعبيرية متاحة فقط داخل مباراة نشطة — ابدأ مباراة أولاً.', "tr": 'Sohbet ve emoji sadece aktif bir oyun içinde kullanılabilir — önce bir oyun başlat.', "ru": 'Чат и эмодзи доступны только во время активной игры — сначала начните игру.',
    },
    "soc_report_title": {
        "fa": 'گزارش این بازیکن', "en": 'Report this player', "ar": 'الإبلاغ عن هذا اللاعب', "tr": 'Bu oyuncuyu bildir', "ru": 'Пожаловаться на игрока',
    },
    "soc_msg_placeholder": {
        "fa": 'پیام بنویس...', "en": 'Write a message...', "ar": 'اكتب رسالة...', "tr": 'Bir mesaj yaz...', "ru": 'Напишите сообщение...',
    },
    "soc_send_btn": {
        "fa": 'ارسال', "en": 'Send', "ar": 'إرسال', "tr": 'Gönder', "ru": 'Отправить',
    },
    "soc_playerid_placeholder": {
        "fa": 'آی\u200cدی بازیکن (playerId)', "en": 'Player ID (playerId)', "ar": 'معرّف اللاعب (playerId)', "tr": 'Oyuncu kimliği (playerId)', "ru": 'ID игрока (playerId)',
    },
    "soc_add_btn": {
        "fa": 'افزودن', "en": 'Add', "ar": 'إضافة', "tr": 'Ekle', "ru": 'Добавить',
    },
    "soc_your_id": {
        "fa": 'آی\u200cدی خودت (برای اشتراک با دوستت):', "en": 'Your ID (to share with a friend):', "ar": 'معرّفك (للمشاركة مع صديقك):', "tr": 'Kimliğin (arkadaşınla paylaşmak için):', "ru": 'Ваш ID (чтобы поделиться с другом):',
    },
    "soc_no_friends": {
        "fa": 'هنوز دوستی اضافه نکردی.', "en": "You haven't added any friends yet.", "ar": 'لم تضف أي أصدقاء بعد.', "tr": 'Henüz arkadaş eklemedin.', "ru": 'Вы ещё не добавили друзей.',
    },
    "soc_clan_name_placeholder": {
        "fa": 'نام باشگاه جدید', "en": 'New clan name', "ar": 'اسم العشيرة الجديدة', "tr": 'Yeni klan adı', "ru": 'Название нового клана',
    },
    "soc_create_btn": {
        "fa": 'ساخت', "en": 'Create', "ar": 'إنشاء', "tr": 'Oluştur', "ru": 'Создать',
    },
    "soc_clan_code_placeholder": {
        "fa": 'کد باشگاه دوستت', "en": "Your friend's clan code", "ar": 'رمز عشيرة صديقك', "tr": 'Arkadaşının klan kodu', "ru": 'Код клана друга',
    },
    "soc_join_btn": {
        "fa": 'پیوستن', "en": 'Join', "ar": 'انضمام', "tr": 'Katıl', "ru": 'Присоединиться',
    },
    "soc_clan_level": {
        "fa": 'لول', "en": 'Level', "ar": 'المستوى', "tr": 'Seviye', "ru": 'Уровень',
    },
    "soc_invite_code": {
        "fa": 'کد دعوت:', "en": 'Invite code:', "ar": 'رمز الدعوة:', "tr": 'Davet kodu:', "ru": 'Код приглашения:',
    },
    "soc_leave_clan": {
        "fa": 'خروج از باشگاه', "en": 'Leave clan', "ar": 'مغادرة العشيرة', "tr": 'Klandan ayrıl', "ru": 'Покинуть клан',
    },
    "soc_gift_note": {
        "fa": 'فقط به دوستانت (که آنلاین هستن) میشه هدیه داد — روزی یک بار.', "en": 'You can only gift friends who are online — once a day.', "ar": 'يمكنك فقط إهداء الأصدقاء المتصلين — مرة واحدة يومياً.', "tr": 'Sadece çevrimiçi arkadaşlarına hediye verebilirsin — günde bir kez.', "ru": 'Дарить можно только друзьям онлайн — раз в день.',
    },
    "soc_add_friend_first": {
        "fa": 'اول یک دوست اضافه کن.', "en": 'Add a friend first.', "ar": 'أضف صديقاً أولاً.', "tr": 'Önce bir arkadaş ekle.', "ru": 'Сначала добавьте друга.',
    },
    "soc_gift_btn": {
        "fa": 'هدیه', "en": 'Gift', "ar": 'هدية', "tr": 'Hediye', "ru": 'Подарок',
    },
    "trn_eliminated": {
        "fa": 'متأسفانه از تورنمنت حذف شدی — دفعه بعد بهتر میشه!', "en": "Unfortunately you've been eliminated from the tournament — better luck next time!", "ar": 'للأسف تم إقصاؤك من البطولة — حظ أوفر في المرة القادمة!', "tr": 'Maalesef turnuvadan elendin — bir dahaki sefere daha iyi olacak!', "ru": 'К сожалению, вы выбыли из турнира — в следующий раз повезёт больше!',
    },
    "trn_prize_coins": {
        "fa": '+{coins} سکه', "en": '+{coins} coins', "ar": '+{coins} عملة', "tr": '+{coins} jeton', "ru": '+{coins} монет',
    },
    "trn_prize_gems": {
        "fa": '، +{gems} جم', "en": ', +{gems} gems', "ar": '، +{gems} جوهرة', "tr": ', +{gems} elmas', "ru": ', +{gems} кристаллов',
    },
    "trn_finished": {
        "fa": 'تورنمنت تموم شد — مقام {place} 🏆 ({prize})', "en": 'Tournament finished — place {place} 🏆 ({prize})', "ar": 'انتهت البطولة — المركز {place} 🏆 ({prize})', "tr": 'Turnuva bitti — {place}. sıra 🏆 ({prize})', "ru": 'Турнир завершён — место {place} 🏆 ({prize})',
    },
    "trn_fab_label": {
        "fa": 'تورنمنت', "en": 'Tournament', "ar": 'البطولة', "tr": 'Turnuva', "ru": 'Турнир',
    },
    "trn_title": {
        "fa": 'تورنمنت\u200cها و لیدربورد', "en": 'Tournaments & leaderboard', "ar": 'البطولات ولوحة المتصدرين', "tr": 'Turnuvalar ve lider tablosu', "ru": 'Турниры и таблица лидеров',
    },
    "trn_tab_current": {
        "fa": 'تورنمنت من', "en": 'My tournament', "ar": 'بطولتي', "tr": 'Turnuvam', "ru": 'Мой турнир',
    },
    "trn_tab_browse": {
        "fa": 'لیست / ساخت', "en": 'Browse / create', "ar": 'تصفح / إنشاء', "tr": 'Listele / oluştur', "ru": 'Список / создать',
    },
    "trn_tab_leaderboard": {
        "fa": 'لیدربورد جهانی', "en": 'Global leaderboard', "ar": 'لوحة المتصدرين العالمية', "tr": 'Küresel lider tablosu', "ru": 'Мировая таблица лидеров',
    },
    "trn_none": {
        "fa": 'توی هیچ تورنمنتی نیستی — از تب «لیست / ساخت» یکی بساز یا بهش بپیوند.', "en": 'You\'re not in any tournament — create or join one from the "Browse / create" tab.', "ar": 'لست في أي بطولة — أنشئ واحدة أو انضم إليها من تبويب "تصفح / إنشاء".', "tr": 'Herhangi bir turnuvada değilsin — "Listele / oluştur" sekmesinden bir tane oluştur ya da katıl.', "ru": 'Вы не участвуете ни в одном турнире — создайте или присоединитесь на вкладке «Список / создать».',
    },
    "trn_status_registration": {
        "fa": 'در حال ثبت\u200cنام', "en": 'Registration open', "ar": 'التسجيل مفتوح', "tr": 'Kayıt açık', "ru": 'Идёт регистрация',
    },
    "trn_status_active": {
        "fa": 'در حال برگزاری', "en": 'In progress', "ar": 'جارية', "tr": 'Devam ediyor', "ru": 'Проходит',
    },
    "trn_status_finished": {
        "fa": 'تمام\u200cشده', "en": 'Finished', "ar": 'منتهية', "tr": 'Bitti', "ru": 'Завершён',
    },
    "trn_mode_knockout": {
        "fa": 'حذفی', "en": 'Knockout', "ar": 'إقصائية', "tr": 'Eleme', "ru": 'На выбывание',
    },
    "trn_mode_league": {
        "fa": 'لیگ', "en": 'League', "ar": 'دوري', "tr": 'Lig', "ru": 'Лига',
    },
    "trn_capacity": {
        "fa": 'ظرفیت', "en": 'capacity', "ar": 'السعة', "tr": 'kapasite', "ru": 'вместимость',
    },
    "trn_start_btn": {
        "fa": 'شروع دستی تورنمنت', "en": 'Start tournament manually', "ar": 'بدء البطولة يدوياً', "tr": 'Turnuvayı manuel başlat', "ru": 'Запустить турнир вручную',
    },
    "trn_withdraw_btn": {
        "fa": 'انصراف از ثبت\u200cنام', "en": 'Withdraw registration', "ar": 'إلغاء التسجيل', "tr": 'Kaydı iptal et', "ru": 'Отменить регистрацию',
    },
    "trn_points_wl": {
        "fa": '{points} امتیاز ({w}ب/{l}ش)', "en": '{points} pts ({w}W/{l}L)', "ar": '{points} نقطة ({w}ف/{l}خ)', "tr": '{points} puan ({w}G/{l}M)', "ru": '{points} очков ({w}П/{l}П)',
    },
    "trn_new_name_placeholder": {
        "fa": 'نام تورنمنت جدید', "en": 'New tournament name', "ar": 'اسم البطولة الجديدة', "tr": 'Yeni turnuva adı', "ru": 'Название нового турнира',
    },
    "trn_size_4": {
        "fa": '۴ نفره', "en": '4 players', "ar": '4 لاعبين', "tr": '4 kişilik', "ru": '4 игрока',
    },
    "trn_size_8": {
        "fa": '۸ نفره', "en": '8 players', "ar": '8 لاعبين', "tr": '8 kişilik', "ru": '8 игроков',
    },
    "trn_size_16": {
        "fa": '۱۶ نفره', "en": '16 players', "ar": '16 لاعباً', "tr": '16 kişilik', "ru": '16 игроков',
    },
    "trn_size_32": {
        "fa": '۳۲ نفره', "en": '32 players', "ar": '32 لاعباً', "tr": '32 kişilik', "ru": '32 игрока',
    },
    "trn_mode_league_option": {
        "fa": 'لیگ (امتیازی)', "en": 'League (points)', "ar": 'دوري (نقاط)', "tr": 'Lig (puanlı)', "ru": 'Лига (очковая)',
    },
    "trn_create_btn": {
        "fa": 'ساخت تورنمنت', "en": 'Create tournament', "ar": 'إنشاء بطولة', "tr": 'Turnuva oluştur', "ru": 'Создать турнир',
    },
    "trn_no_open": {
        "fa": 'الان تورنمنت بازی برای ثبت\u200cنام نیست — یکی بساز!', "en": 'No open tournaments right now — create one!', "ar": 'لا توجد بطولات مفتوحة الآن — أنشئ واحدة!', "tr": 'Şu an açık turnuva yok — bir tane oluştur!', "ru": 'Сейчас нет открытых турниров — создайте свой!',
    },
    "trn_people_suffix": {
        "fa": 'نفر', "en": 'players', "ar": 'لاعبين', "tr": 'kişi', "ru": 'игроков',
    },
    "trn_join_btn": {
        "fa": 'پیوستن', "en": 'Join', "ar": 'انضمام', "tr": 'Katıl', "ru": 'Присоединиться',
    },
    "trn_no_ranked": {
        "fa": 'هنوز کسی رتبه\u200cبندی نشده.', "en": 'No one is ranked yet.', "ar": 'لم يتم تصنيف أحد بعد.', "tr": 'Henüz kimse sıralanmadı.', "ru": 'Пока никто не в рейтинге.',
    },
    "worldcup_fab_label": {
        "fa": 'جهانی', "en": 'World Cup', "ar": 'العالمية', "tr": 'Dünya Kupası', "ru": 'Чемпионат мира',
    },
    "worldcup_wins_suffix": {
        "fa": 'برد', "en": 'wins', "ar": 'فوز', "tr": 'galibiyet', "ru": 'побед',
    },
    "worldcup_eliminated_badge": {
        "fa": 'حذف', "en": 'Out', "ar": 'إقصاء', "tr": 'Elendi', "ru": 'Выбыл',
    },
    "mon_days_hours": {
        "fa": '{d} روز و {h} ساعت', "en": '{d}d {h}h', "ar": '{d} يوم و {h} ساعة', "tr": '{d} gün {h} saat', "ru": '{d} д {h} ч',
    },
    "mon_hours": {
        "fa": '{h} ساعت', "en": '{h}h', "ar": '{h} ساعة', "tr": '{h} saat', "ru": '{h} ч',
    },
    "mon_less_than_hour": {
        "fa": 'کمتر از ۱ ساعت', "en": 'Less than 1 hour', "ar": 'أقل من ساعة', "tr": '1 saatten az', "ru": 'Меньше 1 часа',
    },
    "mon_bp_tier_up": {
        "fa": 'مرحله جدید پس نبرد باز شد: مرحله {tier} 🎉', "en": 'New battle pass tier unlocked: tier {tier} 🎉', "ar": 'تم فتح مستوى جديد من ممر المعارك: المستوى {tier} 🎉', "tr": 'Yeni savaş bileti seviyesi açıldı: seviye {tier} 🎉', "ru": 'Открыт новый уровень боевого пропуска: {tier} 🎉',
    },
    "mon_ad_reward": {
        "fa": 'از تبلیغ گرفتی: {coins} سکه', "en": 'You got from the ad: {coins} coins', "ar": 'حصلت من الإعلان على: {coins} عملة', "tr": 'Reklamdan aldın: {coins} jeton', "ru": 'За рекламу получено: {coins} монет',
    },
    "mon_ad_unavailable": {
        "fa": 'نمیشه الان تبلیغ دید', "en": "Can't watch an ad right now", "ar": 'لا يمكن مشاهدة إعلان الآن', "tr": 'Şu an reklam izlenemiyor', "ru": 'Сейчас нельзя посмотреть рекламу',
    },
    "mon_vip_activated": {
        "fa": 'VIP {plan} فعال شد!', "en": 'VIP {plan} activated!', "ar": 'تم تفعيل VIP {plan}!', "tr": 'VIP {plan} etkinleştirildi!', "ru": 'VIP {plan} активирован!',
    },
    "mon_vip_buy_error": {
        "fa": 'خطا در خرید VIP', "en": 'Error purchasing VIP', "ar": 'خطأ في شراء VIP', "tr": 'VIP satın alma hatası', "ru": 'Ошибка покупки VIP',
    },
    "mon_vip_daily_reward": {
        "fa": 'جایزه روزانه VIP: {coins} سکه', "en": 'VIP daily reward: {coins} coins', "ar": 'مكافأة VIP اليومية: {coins} عملة', "tr": 'VIP günlük ödülü: {coins} jeton', "ru": 'Ежедневная награда VIP: {coins} монет',
    },
    "mon_vip_daily_error": {
        "fa": 'خطا در دریافت جایزه VIP', "en": 'Error claiming VIP reward', "ar": 'خطأ في استلام مكافأة VIP', "tr": 'VIP ödülü alınırken hata', "ru": 'Ошибка получения награды VIP',
    },
    "mon_gems_added": {
        "fa": '{gems} جم اضافه شد', "en": '{gems} gems added', "ar": 'تمت إضافة {gems} جوهرة', "tr": '{gems} elmas eklendi', "ru": 'Добавлено {gems} кристаллов',
    },
    "mon_gem_buy_error": {
        "fa": 'خطا در خرید جم', "en": 'Error purchasing gems', "ar": 'خطأ في شراء الجواهر', "tr": 'Elmas satın alma hatası', "ru": 'Ошибка покупки кристаллов',
    },
    "mon_bp_premium_activated": {
        "fa": 'پس پریمیوم فعال شد! 👑', "en": 'Premium pass activated! 👑', "ar": 'تم تفعيل الممر المميز! 👑', "tr": 'Premium bilet etkinleştirildi! 👑', "ru": 'Премиум-пропуск активирован! 👑',
    },
    "mon_bp_premium_error": {
        "fa": 'خطا در خرید پس پریمیوم', "en": 'Error purchasing premium pass', "ar": 'خطأ في شراء الممر المميز', "tr": 'Premium bilet satın alma hatası', "ru": 'Ошибка покупки премиум-пропуска',
    },
    "mon_bp_reward_claimed": {
        "fa": 'جایزه پس نبرد دریافت شد 🎁', "en": 'Battle pass reward claimed 🎁', "ar": 'تم استلام مكافأة ممر المعارك 🎁', "tr": 'Savaş bileti ödülü alındı 🎁', "ru": 'Награда боевого пропуска получена 🎁',
    },
    "mon_claim_error": {
        "fa": 'خطا در دریافت جایزه', "en": 'Error claiming reward', "ar": 'خطأ في استلام الجائزة', "tr": 'Ödül alınırken hata', "ru": 'Ошибка получения награды',
    },
    "mon_fab_label": {
        "fa": 'VIP و پس نبرد', "en": 'VIP & battle pass', "ar": 'VIP وممر المعارك', "tr": 'VIP ve savaş bileti', "ru": 'VIP и боевой пропуск',
    },
    "mon_title": {
        "fa": 'VIP و پس نبرد', "en": 'VIP & battle pass', "ar": 'VIP وممر المعارك', "tr": 'VIP ve savaş bileti', "ru": 'VIP и боевой пропуск',
    },
    "mon_tab_battlepass": {
        "fa": 'پس نبرد', "en": 'Battle pass', "ar": 'ممر المعارك', "tr": 'Savaş bileti', "ru": 'Боевой пропуск',
    },
    "mon_tab_gems": {
        "fa": 'فروشگاه جم', "en": 'Gem shop', "ar": 'متجر الجواهر', "tr": 'Elmas mağazası', "ru": 'Магазин кристаллов',
    },
    "mon_tab_ads": {
        "fa": 'تبلیغ', "en": 'Ads', "ar": 'الإعلانات', "tr": 'Reklamlar', "ru": 'Реклама',
    },
    "mon_vip_active": {
        "fa": 'عضو VIP هستی — {time} باقی مانده', "en": "You're a VIP member — {time} remaining", "ar": 'أنت عضو VIP — تبقى {time}', "tr": 'VIP üyesisin — {time} kaldı', "ru": 'Вы VIP-участник — осталось {time}',
    },
    "mon_vip_not_active": {
        "fa": 'هنوز VIP نیستی', "en": "You're not a VIP yet", "ar": 'لست عضو VIP بعد', "tr": 'Henüz VIP değilsin', "ru": 'Вы ещё не VIP',
    },
    "mon_vip_daily_title": {
        "fa": 'جایزه روزانه VIP', "en": 'VIP daily reward', "ar": 'مكافأة VIP اليومية', "tr": 'VIP günlük ödülü', "ru": 'Ежедневная награда VIP',
    },
    "mon_vip_daily_desc": {
        "fa": '{coins} سکه رایگان هر روز برای اعضای VIP', "en": '{coins} free coins every day for VIP members', "ar": '{coins} عملة مجانية يومياً لأعضاء VIP', "tr": 'VIP üyelere her gün {coins} ücretsiz jeton', "ru": '{coins} бесплатных монет каждый день для VIP',
    },
    "mon_vip_only": {
        "fa": 'فقط VIP', "en": 'VIP only', "ar": 'لأعضاء VIP فقط', "tr": 'Sadece VIP', "ru": 'Только для VIP',
    },
    "mon_claim_btn": {
        "fa": 'دریافت', "en": 'Claim', "ar": 'استلام', "tr": 'Al', "ru": 'Забрать',
    },
    "mon_claimed_btn": {
        "fa": 'دریافت شد', "en": 'Claimed', "ar": 'تم الاستلام', "tr": 'Alındı', "ru": 'Получено',
    },
    "mon_vip_perks": {
        "fa": 'مزایای VIP: ۱٫۲۵× سکه و ۱٫۱۵× XP در پایان هر بازی، به\u200cعلاوه جایزه روزانه.', "en": 'VIP perks: 1.25× coins and 1.15× XP at the end of every match, plus a daily reward.', "ar": 'مزايا VIP: 1.25× عملات و1.15× XP في نهاية كل مباراة، بالإضافة إلى مكافأة يومية.', "tr": 'VIP avantajları: her maç sonunda 1.25× jeton ve 1.15× XP, artı günlük ödül.', "ru": 'Преимущества VIP: 1,25× монет и 1,15× опыта за каждый матч, плюс ежедневная награда.',
    },
    "mon_toman": {
        "fa": 'تومان', "en": 'Toman', "ar": 'تومان', "tr": 'Toman', "ru": 'томан',
    },
    "mon_buy_btn": {
        "fa": 'خرید', "en": 'Buy', "ar": 'شراء', "tr": 'Satın al', "ru": 'Купить',
    },
    "mon_bp_tier_label": {
        "fa": 'مرحله', "en": 'Tier', "ar": 'المستوى', "tr": 'Seviye', "ru": 'Уровень',
    },
    "mon_bp_premium_active": {
        "fa": 'پریمیوم فعال 👑', "en": 'Premium active 👑', "ar": 'المميز مفعّل 👑', "tr": 'Premium aktif 👑', "ru": 'Премиум активен 👑',
    },
    "mon_bp_free_only": {
        "fa": 'فقط رایگان', "en": 'Free only', "ar": 'مجاني فقط', "tr": 'Sadece ücretsiz', "ru": 'Только бесплатный',
    },
    "mon_bp_buy_premium_title": {
        "fa": 'خرید مسیر پریمیوم', "en": 'Buy premium track', "ar": 'شراء المسار المميز', "tr": 'Premium yolu satın al', "ru": 'Купить премиум-путь',
    },
    "mon_bp_buy_premium_desc": {
        "fa": 'جوایز دو برابر بهتر در همه مراحل', "en": 'Twice-as-good rewards at every tier', "ar": 'مكافآت أفضل بمرتين في كل المستويات', "tr": 'Her seviyede iki kat daha iyi ödüller', "ru": 'Вдвое лучшие награды на каждом уровне',
    },
    "mon_special_item": {
        "fa": 'آیتم ویژه', "en": 'Special item', "ar": 'عنصر خاص', "tr": 'Özel eşya', "ru": 'Особый предмет',
    },
    "mon_claimed_btn2": {
        "fa": 'گرفته شد', "en": 'Claimed', "ar": 'تم الاستلام', "tr": 'Alındı', "ru": 'Получено',
    },
    "mon_bonus": {
        "fa": 'هدیه', "en": 'bonus', "ar": 'مكافأة', "tr": 'bonus', "ru": 'бонус',
    },
    "mon_ad_prompt": {
        "fa": 'یک تبلیغ کوتاه ببین و {coins} سکه بگیر', "en": 'Watch a short ad and get {coins} coins', "ar": 'شاهد إعلاناً قصيراً واحصل على {coins} عملة', "tr": 'Kısa bir reklam izle ve {coins} jeton kazan', "ru": 'Посмотрите короткую рекламу и получите {coins} монет',
    },
    "mon_today": {
        "fa": 'امروز:', "en": 'Today:', "ar": 'اليوم:', "tr": 'Bugün:', "ru": 'Сегодня:',
    },
    "mon_watch_ad_btn": {
        "fa": 'تماشای تبلیغ', "en": 'Watch ad', "ar": 'مشاهدة الإعلان', "tr": 'Reklamı izle', "ru": 'Смотреть рекламу',
    },
    "mon_ad_cap_reached": {
        "fa": 'سقف امروز تمام شد', "en": "Today's limit reached", "ar": 'تم بلوغ حد اليوم', "tr": 'Bugünkü limit doldu', "ru": 'Дневной лимит исчерпан',
    },
    "stt_you": {
        "fa": 'شما', "en": 'You', "ar": 'أنت', "tr": 'Sen', "ru": 'Вы',
    },
    "stt_suggestion": {
        "fa": '💡 پیشنهاد: {card} — {reason}', "en": '💡 Suggestion: {card} — {reason}', "ar": '💡 اقتراح: {card} — {reason}', "tr": '💡 Öneri: {card} — {reason}', "ru": '💡 Совет: {card} — {reason}',
    },
    "stt_suggestion_needs_turn": {
        "fa": 'الان نوبت توئه که این پیشنهاد معنی داشته باشه.', "en": 'It needs to be your turn for a suggestion to make sense.', "ar": 'يجب أن يكون دورك حتى يكون للاقتراح معنى.', "tr": 'Önerinin anlamlı olması için sıranın sende olması gerekir.', "ru": 'Совет имеет смысл только когда ваш ход.',
    },
    "stt_fab_label": {
        "fa": 'آمار', "en": 'Stats', "ar": 'الإحصائيات', "tr": 'İstatistikler', "ru": 'Статистика',
    },
    "stt_title": {
        "fa": 'آمار، تاریخچه و لیدربورد', "en": 'Stats, history & leaderboard', "ar": 'الإحصائيات والتاريخ ولوحة المتصدرين', "tr": 'İstatistikler, geçmiş ve lider tablosu', "ru": 'Статистика, история и рейтинг',
    },
    "stt_tab_stats": {
        "fa": 'آمار من', "en": 'My stats', "ar": 'إحصائياتي', "tr": 'İstatistiklerim', "ru": 'Моя статистика',
    },
    "stt_tab_history": {
        "fa": 'تاریخچه / ریپلی', "en": 'History / replay', "ar": 'التاريخ / الإعادة', "tr": 'Geçmiş / tekrar', "ru": 'История / повтор',
    },
    "stt_tab_leaderboard": {
        "fa": 'لیدربورد', "en": 'Leaderboard', "ar": 'لوحة المتصدرين', "tr": 'Lider tablosu', "ru": 'Рейтинг',
    },
    "stt_hint_btn": {
        "fa": 'پیشنهاد حرکت (فقط سر نوبت خودت)', "en": 'Suggest a move (only on your turn)', "ar": 'اقتراح حركة (فقط في دورك)', "tr": 'Hamle öner (sadece sıran geldiğinde)', "ru": 'Подсказать ход (только в свой ход)',
    },
    "stt_no_stats": {
        "fa": 'هنوز آماری ثبت نشده — یک مسابقه بازی کن!', "en": 'No stats recorded yet — play a match!', "ar": 'لم يتم تسجيل أي إحصائيات بعد — العب مباراة!', "tr": 'Henüz istatistik kaydedilmedi — bir maç oyna!', "ru": 'Статистики пока нет — сыграйте матч!',
    },
    "stt_stat_matches": {
        "fa": 'مسابقات', "en": 'Matches', "ar": 'المباريات', "tr": 'Maçlar', "ru": 'Матчи',
    },
    "stt_stat_wins": {
        "fa": 'بردها', "en": 'Wins', "ar": 'الانتصارات', "tr": 'Galibiyetler', "ru": 'Победы',
    },
    "stt_stat_winrate": {
        "fa": 'درصد برد', "en": 'Win rate', "ar": 'نسبة الفوز', "tr": 'Kazanma oranı', "ru": 'Процент побед',
    },
    "stt_stat_tricks": {
        "fa": 'برگ\u200cهای برده', "en": 'Tricks won', "ar": 'الخدع المكسوبة', "tr": 'Kazanılan eller', "ru": 'Взятки',
    },
    "stt_stat_sur": {
        "fa": 'سور', "en": 'Sur (shutouts)', "ar": 'سور', "tr": 'Sur', "ru": 'Сур',
    },
    "stt_stat_hakem_winrate": {
        "fa": 'درصد برد به\u200cعنوان حاکم', "en": 'Win rate as hakem', "ar": 'نسبة الفوز كحاكم', "tr": 'Hakem olarak kazanma oranı', "ru": 'Процент побед в роли хакима',
    },
    "stt_stat_best_streak": {
        "fa": 'بهترین رکورد برد پیاپی', "en": 'Best win streak', "ar": 'أفضل سلسلة انتصارات', "tr": 'En iyi galibiyet serisi', "ru": 'Лучшая победная серия',
    },
    "stt_stat_sur_rate": {
        "fa": 'درصد سور از دست\u200cهای برده', "en": 'Sur rate among won hands', "ar": 'نسبة السور من الجولات المكسوبة', "tr": 'Kazanılan ellerde sur oranı', "ru": 'Доля сур среди выигранных раздач',
    },
    "stt_no_matches": {
        "fa": 'هنوز مسابقه\u200cای تموم نشده.', "en": 'No matches finished yet.', "ar": 'لم تنته أي مباراة بعد.', "tr": 'Henüz biten maç yok.', "ru": 'Матчи ещё не завершены.',
    },
    "stt_win_badge": {
        "fa": 'برد', "en": 'Win', "ar": 'فوز', "tr": 'Galibiyet', "ru": 'Победа',
    },
    "stt_loss_badge": {
        "fa": 'باخت', "en": 'Loss', "ar": 'خسارة', "tr": 'Mağlubiyet', "ru": 'Поражение',
    },
    "stt_hands_score": {
        "fa": 'امتیاز دست\u200cها:', "en": 'Hands score:', "ar": 'نتيجة الجولات:', "tr": 'El skoru:', "ru": 'Счёт раздач:',
    },
    "stt_optimal_rate": {
        "fa": 'بهینه:', "en": 'optimal:', "ar": 'الأمثل:', "tr": 'optimal:', "ru": 'оптимально:',
    },
    "stt_view_replay": {
        "fa": 'دیدن ریپلی', "en": 'View replay', "ar": 'مشاهدة الإعادة', "tr": 'Tekrarı izle', "ru": 'Смотреть повтор',
    },
    "stt_back_to_history": {
        "fa": 'بازگشت به تاریخچه', "en": 'Back to history', "ar": 'العودة إلى التاريخ', "tr": 'Geçmişe dön', "ru": 'Назад к истории',
    },
    "stt_replay_not_found": {
        "fa": 'این ریپلی پیدا نشد.', "en": "This replay wasn't found.", "ar": 'لم يتم العثور على هذه الإعادة.', "tr": 'Bu tekrar bulunamadı.', "ru": 'Повтор не найден.',
    },
    "stt_smart_analysis": {
        "fa": 'تحلیل هوشمند (بهینه: {rate}%)', "en": 'Smart analysis (optimal: {rate}%)', "ar": 'تحليل ذكي (الأمثل: {rate}%)', "tr": 'Akıllı analiz (optimal: %{rate})', "ru": 'Умный анализ (оптимально: {rate}%)',
    },
    "stt_hand_label": {
        "fa": 'دست', "en": 'Hand', "ar": 'الجولة', "tr": 'El', "ru": 'Раздача',
    },
    "stt_hakem_label": {
        "fa": 'حاکم:', "en": 'hakem:', "ar": 'الحاكم:', "tr": 'hakem:', "ru": 'хаким:',
    },
    "stt_trump_label": {
        "fa": 'حکم:', "en": 'trump:', "ar": 'الورقة الرابحة:', "tr": 'koz:', "ru": 'козырь:',
    },
    "stt_result_label": {
        "fa": 'نتیجه:', "en": 'result:', "ar": 'النتيجة:', "tr": 'sonuç:', "ru": 'результат:',
    },
    "stt_no_ranked": {
        "fa": 'هنوز کسی مسابقه\u200cای تموم نکرده.', "en": 'No one has finished a match yet.', "ar": 'لم ينه أحد مباراة بعد.', "tr": 'Henüz kimse maç bitirmedi.', "ru": 'Пока никто не завершил матч.',
    },
    "stt_wins_pct": {
        "fa": '{wins} برد ({rate}%)', "en": '{wins} wins ({rate}%)', "ar": '{wins} فوز ({rate}%)', "tr": '{wins} galibiyet (%{rate})', "ru": '{wins} побед ({rate}%)',
    },
    "ach_cat_wins": {
        "fa": 'بردها', "en": 'Wins', "ar": 'الانتصارات', "tr": 'Galibiyetler', "ru": 'Победы',
    },
    "ach_cat_tricks": {
        "fa": 'خشت\u200cها', "en": 'Tricks', "ar": 'الخدع', "tr": 'Eller', "ru": 'Взятки',
    },
    "ach_cat_sur": {
        "fa": 'سور', "en": 'Sur', "ar": 'سور', "tr": 'Sur', "ru": 'Сур',
    },
    "ach_cat_hakem": {
        "fa": 'حاکم', "en": 'Hakem', "ar": 'الحاكم', "tr": 'Hakem', "ru": 'Хаким',
    },
    "ach_cat_streak": {
        "fa": 'برد پیاپی', "en": 'Win streak', "ar": 'سلسلة انتصارات', "tr": 'Galibiyet serisi', "ru": 'Победная серия',
    },
    "ach_cat_level": {
        "fa": 'لول', "en": 'Level', "ar": 'المستوى', "tr": 'Seviye', "ru": 'Уровень',
    },
    "ach_cat_rank": {
        "fa": 'رتبه', "en": 'Rank', "ar": 'الرتبة', "tr": 'Rütbe', "ru": 'Ранг',
    },
    "ach_cat_social": {
        "fa": 'اجتماعی', "en": 'Social', "ar": 'اجتماعي', "tr": 'Sosyal', "ru": 'Общение',
    },
    "ach_cat_worldcup": {
        "fa": 'جام جهانی', "en": 'World Cup', "ar": 'العالمية', "tr": 'Dünya Kupası', "ru": 'Чемпионат мира',
    },
    "ach_cat_collector": {
        "fa": 'کلکسیون', "en": 'Collector', "ar": 'مجموعة', "tr": 'Koleksiyon', "ru": 'Коллекция',
    },
    "ach_claimed": {
        "fa": 'دستاورد دریافت شد: {coins} سکه', "en": 'Achievement claimed: {coins} coins', "ar": 'تم استلام الإنجاز: {coins} عملة', "tr": 'Başarım alındı: {coins} jeton', "ru": 'Достижение получено: {coins} монет',
    },
    "ach_xp_suffix": {
        "fa": '، {xp} XP', "en": ', {xp} XP', "ar": '، {xp} XP', "tr": ', {xp} XP', "ru": ', {xp} XP',
    },
    "ach_gems_suffix": {
        "fa": '، {gems} جم', "en": ', {gems} gems', "ar": '، {gems} جوهرة', "tr": ', {gems} elmas', "ru": ', {gems} кристаллов',
    },
    "ach_claim_error": {
        "fa": 'خطا در دریافت دستاورد', "en": 'Error claiming achievement', "ar": 'خطأ في استلام الإنجاز', "tr": 'Başarım alınırken hata', "ru": 'Ошибка получения достижения',
    },
    "ach_title": {
        "fa": 'دستاوردها', "en": 'Achievements', "ar": 'الإنجازات', "tr": 'Başarımlar', "ru": 'Достижения',
    },
    "ach_summary": {
        "fa": '{done} از {total} دریافت شده', "en": '{done} of {total} claimed', "ar": '{done} من {total} تم استلامها', "tr": '{total} üzerinden {done} alındı', "ru": 'Получено {done} из {total}',
    },
    "ach_claimed_btn": {
        "fa": 'دریافت شد', "en": 'Claimed', "ar": 'تم الاستلام', "tr": 'Alındı', "ru": 'Получено',
    },
    "ach_claim_btn": {
        "fa": 'دریافت جایزه', "en": 'Claim reward', "ar": 'استلام الجائزة', "tr": 'Ödülü al', "ru": 'Забрать награду',
    },
    "ach_locked": {
        "fa": 'قفل', "en": 'Locked', "ar": 'مقفل', "tr": 'Kilitli', "ru": 'Заблокировано',
    },
}


def language_list() -> list:
    return [dict(row) for row in LANGUAGES]


def normalize_lang(lang) -> str:
    if isinstance(lang, str) and lang.lower() in _VALID:
        return lang.lower()
    return DEFAULT_LANG


def catalog(lang: str) -> dict:
    lang = normalize_lang(lang)
    return {key: table.get(lang, table[DEFAULT_LANG]) for key, table in _STRINGS.items()}


def t(key: str, lang: str) -> str:
    lang = normalize_lang(lang)
    table = _STRINGS.get(key)
    if not table:
        return key
    return table.get(lang) or table.get(DEFAULT_LANG) or key