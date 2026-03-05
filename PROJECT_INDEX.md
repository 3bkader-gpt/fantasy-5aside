# 📋 فهرس المشروع الشامل - 5-a-Side Fantasy Football SaaS

## 🎯 نظرة عامة على المشروع

**النوع**: تطبيق Fantasy Football متعدد المستأجرين (Multi-Tenant SaaS) مخصص لمباريات 5 ضد 5 المحلية

**التقنيات المستخدمة**:
- **Backend**: FastAPI + Python 3
- **Database**: SQLite (تطوير) / PostgreSQL (إنتاج) + SQLAlchemy ORM
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript + Jinja2 Templates
- **Authentication**: JWT Tokens + Cookie-based sessions
- **Security**: bcrypt password hashing, anti-cheat voting system

**الإصدار الحالي**: v3.0

---

## 📁 الهيكل العام للمشروع

```
fantasy/
├── app/                          # التطبيق الرئيسي
│   ├── main.py                  # نقطة البداية FastAPI
│   ├── database.py              # إعدادات قاعدة البيانات
│   ├── dependencies.py          # Dependency Injection Container
│   │
│   ├── core/                    # الإعدادات الأساسية
│   │   ├── config.py           # إدارة الإعدادات والبيئة
│   │   └── security.py         # JWT + Password Hashing
│   │
│   ├── models/                  # نماذج قاعدة البيانات (SQLAlchemy)
│   │   └── models.py           # جميع الـ Models
│   │
│   ├── schemas/                 # Pydantic Schemas للـ API
│   │   └── schemas.py          # جميع الـ Schemas
│   │
│   ├── repositories/            # طبقة الوصول للبيانات (Repository Pattern)
│   │   ├── interfaces.py       # Abstract interfaces
│   │   └── db_repository.py    # التنفيذ الفعلي
│   │
│   ├── services/                # منطق الأعمال (Business Logic)
│   │   ├── interfaces.py       # Service interfaces
│   │   ├── league_service.py   # إدارة الدوريات والمواسم
│   │   ├── match_service.py    # تسجيل وتعديل المباريات
│   │   ├── cup_service.py      # نظام الكأس (knockout tournament)
│   │   ├── voting_service.py   # نظام التصويت
│   │   ├── analytics_service.py # التحليلات والإحصائيات
│   │   ├── achievements.py     # نظام الشارات والإنجازات
│   │   └── points.py           # حساب النقاط (Strategy Pattern)
│   │
│   ├── routers/                 # API Routes
│   │   ├── public.py           # الصفحات العامة
│   │   ├── admin.py            # لوحة التحكم
│   │   ├── auth.py             # تسجيل الدخول/الخروج
│   │   └── voting.py           # API التصويت
│   │
│   ├── templates/               # Jinja2 HTML Templates
│   │   ├── base.html           # القالب الأساسي
│   │   ├── landing.html        # الصفحة الرئيسية
│   │   ├── leaderboard.html    # جدول الترتيب
│   │   ├── matches.html        # المباريات
│   │   ├── player.html         # ملف اللاعب
│   │   ├── cup.html            # صفحة الكأس
│   │   ├── hof.html            # قاعة المشاهير
│   │   ├── admin/
│   │   │   └── dashboard.html  # لوحة التحكم
│   │   └── auth/
│   │       ├── login.html      # تسجيل الدخول
│   │       └── unauthorized.html
│   │
│   └── static/                  # الملفات الثابتة
│       ├── css/style.css
│       ├── js/
│       │   ├── main.js
│       │   ├── admin_dashboard.js
│       │   ├── leaderboard.js
│       │   ├── matches.js
│       │   └── player_chart.js
│       └── img/
│
├── tests/                       # الاختبارات
│   ├── conftest.py             # إعداد الاختبارات
│   ├── test_points.py          # اختبارات حساب النقاط
│   ├── test_match_service.py   # اختبارات المباريات
│   ├── test_league_service.py  # اختبارات الدوريات
│   ├── test_cup.py             # اختبارات الكأس
│   ├── test_voting_live.py     # اختبارات التصويت
│   └── test_api_*.py           # اختبارات الـ API
│
├── data/                        # قاعدة البيانات المحلية
│   └── fantasy.db              # SQLite DB (للتطوير)
│
├── requirements.txt             # المتطلبات
├── pytest.ini                   # إعدادات الاختبارات
├── render.yaml                  # إعداد النشر على Render
└── SAAS_PLAN.md                # خطة التحول إلى SaaS كامل

```

---

## 🗄️ قاعدة البيانات (Database Schema)

### الجداول الرئيسية:

#### 1. **leagues** (الدوريات)
```python
- id: معرف فريد
- name: اسم الدوري (فريد)
- slug: الرابط النصي (فريد)
- admin_password: كلمة مرور مشفرة للمدير
- current_season_matches: عدد المباريات في الموسم الحالي
- season_number: رقم الموسم
- team_a_label: تسمية الفريق أ
- team_b_label: تسمية الفريق ب
- created_at: تاريخ الإنشاء
```

#### 2. **players** (اللاعبون)
```python
- id, league_id (Foreign Key)
- name: اسم اللاعب
- team_id: الفريق المسجل فيه (اختياري)
- default_is_gk: هل اللاعب حارس مرمى؟

# إحصائيات الموسم الحالي:
- total_points, total_goals, total_assists
- total_saves, total_clean_sheets, total_own_goals
- total_matches, previous_rank

# إحصائيات طوال المسيرة (All-Time):
- all_time_points, all_time_goals, all_time_assists
- all_time_saves, all_time_clean_sheets, all_time_own_goals
- all_time_matches

# للتراجع عن إنهاء الموسم:
- last_season_points, last_season_goals, ...

# للكأس:
- is_active_in_cup: هل مشارك في الكأس الحالي؟
```

#### 3. **teams** (الفرق المسجلة - نظام جديد)
```python
- id, league_id
- name: اسم الفريق
- short_code: الرمز (مثل HR, IT)
- color: اللون بصيغة hex
```

#### 4. **matches** (المباريات)
```python
- id, league_id
- date: تاريخ المباراة
- team_a_name, team_b_name: أسماء الفرق
- team_a_id, team_b_id: معرفات الفرق (إذا كان النظام مفعّل)
- team_a_score, team_b_score: النتيجة
- voting_round: حالة التصويت (0-4)
  * 0 = غير مفتوح
  * 1-3 = جولات التصويت
  * 4 = مغلق
```

#### 5. **match_stats** (إحصائيات اللاعبين في المباريات)
```python
- id, player_id, match_id
- team: A أو B
- goals, assists, saves, goals_conceded, own_goals
- is_winner, is_gk, clean_sheet, mvp, is_captain
- points_earned, bonus_points
```

#### 6. **cup_matchups** (مواجهات الكأس)
```python
- id, league_id
- player1_id, player2_id (nullable - bye)
- round_name: اسم الجولة
- bracket_type: "outfield" أو "goalkeeper"
- winner_id: الفائز
- is_active: هل المواجهة نشطة؟
- is_revealed: هل تم الكشف عنها؟
- match_id: المباراة التي حُسِمت فيها
```

#### 7. **votes** (التصويتات)
```python
- id, league_id, match_id
- voter_id, candidate_id: من صوّت ولمن
- round_number: رقم الجولة (1-3)
- ip_address: عنوان IP (للحماية)
- device_fingerprint: بصمة الجهاز (للحماية)
- created_at
```

#### 8. **hall_of_fame** (قاعة المشاهير)
```python
- id, league_id, player_id
- month_year: اسم الموسم
- points_scored: النقاط التي فاز بها
```

#### 9. **transfers** (الانتقالات بين الفرق)
```python
- id, league_id, player_id
- from_team_id, to_team_id
- reason: سبب الانتقال
- created_at
```

---

## 🎮 الميزات الرئيسية

### 1. **Multi-Tenancy (تعدد المستأجرين)**
- كل دوري معزول تماماً عن الآخرين
- رابط فريد لكل دوري: `/l/{slug}`
- كلمة مرور مستقلة لكل مدير دوري

### 2. **نظام النقاط المتقدم** (app/services/points.py)

استخدام **Strategy Pattern** لحساب النقاط:

#### الاستراتيجيات:
```python
1. ParticipationPoints: +2 لمجرد المشاركة
2. GoalPoints: +3 للهدف (+6 للحارس)
3. AssistPoints: +2 للتمريرة الحاسمة (+4 للحارس)
4. WinPoints: 
   - فوز: +2
   - تعادل: +1
   - خسارة: -1
5. CleanSheetPoints (للحارس):
   - 0-2 أهداف مستقبلة: +10
   - 3-6 أهداف: +4
   - أكثر من 6: 0
6. SavePoints (للحارس): كل 3 تصديات = +2
7. GoalsConcededPenalty (للحارس): كل 4 أهداف = -1
8. OwnGoalPenalty: هدف عكسي = -1
```

### 3. **نظام الكابتن** (Captain System)
- المدير يستطيع تعيين قائد للمباراة
- القائد يحصل على **ضعف النقاط** (×2)

### 4. **نظام الكأس الشهري** (Monthly Cup)
- يتم توليد كأس تلقائي لأفضل 10 لاعبين
- مواجهات مباشرة (Head-to-Head)
- مسارين منفصلين: حراس vs لاعبي خط
- الحسم التلقائي: عندما يلعب اللاعبان في نفس المباراة
- قانون النهائي التعاوني: إذا كانا في نفس الفريق = فوز مشترك

### 5. **نظام التصويت لـ MVP** (Voting System)
- 3 جولات تصويت بعد كل مباراة
- كل جولة تمنح نقاط إضافية:
  - الجولة 1: +3 نقاط
  - الجولة 2: +2 نقاط
  - الجولة 3: +1 نقطة
- حماية ثلاثية من الغش:
  1. **localStorage**: منع التصويت مرتين من نفس المتصفح
  2. **IP Address**: حد أقصى 2 تصويت من نفس IP
  3. **Device Fingerprint**: بصمة الجهاز الفريدة

### 6. **المواسم التلقائية** (Auto Seasons)
- كل 4 مباريات = موسم جديد
- يتم تلقائياً:
  1. حفظ الفائز في قاعة المشاهير
  2. نقل الإحصائيات الحالية إلى All-Time
  3. إعادة تعيين الأرقام للموسم الجديد
- إمكانية التراجع (Undo)

### 7. **نظام الفرق المسجلة** (Fixed Teams)
- تسجيل فرق دائمة (مثل HR, IT, Sales...)
- تتبع اللاعبين وانتماءاتهم
- سجل الانتقالات بين الفرق

### 8. **نظام الشارات** (Achievements/Badges)
شارات تلقائية على الـ Leaderboard:

```python
- 🔫 القناص: 6 أهداف في مباراة واحدة
- 🛡️ الحائط: 3 نظافة شباك
- 🎯 صانع الألعاب: 15 تمريرة حاسمة
- ⚡ الصاروخ: 5 أهداف في 3 مباريات متتالية
- 🤡 مهرج الدفاع: سجل أهداف عكسية
- 🔥 Hot Form: أداء ممتاز في آخر 3 مباريات
- ❄️ Cold Form: أداء ضعيف
```

### 9. **صفحة التحليلات للاعب** (Player Analytics)
- معدل الفوز (Win Rate %)
- Goal Contribution per Match
- رسم بياني للأداء عبر الزمن (Chart.js)
- السجل الكامل للمباريات

---

## 🔧 الأنماط المعمارية المستخدمة

### 1. **Repository Pattern**
فصل منطق الوصول للبيانات عن منطق الأعمال:
```
├── repositories/interfaces.py    → التعريفات (Abstract)
└── repositories/db_repository.py → التنفيذ (Concrete)
```

### 2. **Dependency Injection**
جميع الـ Services والـ Repositories يتم حقنها عبر `dependencies.py`:
```python
get_league_service(...)
get_match_service(...)
get_cup_service(...)
```

### 3. **Strategy Pattern**
في حساب النقاط (`points.py`):
```python
class PointsStrategy(ABC):
    @abstractmethod
    def calculate(self, ctx: PointsContext) -> int:
        pass
```

### 4. **Service Layer Pattern**
منطق الأعمال معزول في طبقة الـ Services:
- LeagueService
- MatchService
- CupService
- VotingService
- AnalyticsService

---

## 🛣️ المسارات (API Routes)

### Public Routes (`routers/public.py`):
```
GET  /                             → الصفحة الرئيسية
POST /create-league                → إنشاء دوري جديد
GET  /l/{slug}                     → جدول الترتيب
GET  /l/{slug}/matches             → المباريات
GET  /l/{slug}/cup                 → الكأس
GET  /l/{slug}/player/{id}         → ملف اللاعب
GET  /l/{slug}/hof                 → قاعة المشاهير
```

### Admin Routes (`routers/admin.py`) - تحتاج JWT:
```
GET  /l/{slug}/admin               → لوحة التحكم
POST /l/{slug}/admin/match         → تسجيل مباراة
PUT  /l/{slug}/admin/match/{id}    → تعديل مباراة
DELETE /l/{slug}/admin/match/{id}  → حذف مباراة
POST /l/{slug}/admin/cup/generate  → توليد الكأس
POST /l/{slug}/admin/season/end    → إنهاء الموسم
POST /l/{slug}/admin/season/undo   → التراجع عن إنهاء
POST /l/{slug}/admin/settings/update → تحديث الإعدادات
POST /l/{slug}/admin/player/add    → إضافة لاعب
PUT  /l/{slug}/admin/player/{id}   → تعديل لاعب
DELETE /l/{slug}/admin/player/{id} → حذف لاعب
POST /l/{slug}/admin/team/create   → إنشاء فريق
```

### Auth Routes (`routers/auth.py`):
```
GET  /login                        → صفحة تسجيل الدخول
POST /login                        → تسجيل الدخول
GET  /logout                       → تسجيل الخروج
```

### Voting API (`routers/voting.py`):
```
GET  /api/voting/match/{id}/status → حالة التصويت
GET  /api/voting/match/{id}/live   → الإحصائيات الحية
POST /api/voting/vote              → إرسال تصويت
POST /api/voting/{slug}/open/{id}  → فتح التصويت (Admin)
POST /api/voting/{slug}/close/{id} → إغلاق الجولة (Admin)
```

---

## 🔒 الأمان (Security)

### 1. **JWT Authentication**
```python
# في core/security.py:
- create_access_token(): إنشاء token
- verify_token(): التحقق من صلاحية token
- صلاحية الـ token: 7 أيام
```

### 2. **Password Hashing**
```python
# استخدام passlib + bcrypt:
- get_password_hash(): تشفير كلمة المرور
- verify_password(): التحقق
```

### 3. **Cookie-based Sessions**
```python
# الـ JWT يُحفظ في cookie httpOnly:
response.set_cookie(
    key="access_token",
    value=f"Bearer {token}",
    httponly=True,
    samesite="lax"
)
```

### 4. **Anti-Cheat في التصويت**
```python
# طبقات الحماية:
1. localStorage: منع التكرار في المتصفح
2. IP Limit: حد أقصى 2 صوت من نفس IP
3. Fingerprint: بصمة الجهاز الفريدة
```

---

## 🧪 الاختبارات (Tests)

```
tests/
├── conftest.py                  → إعداد fixtures
├── test_points.py              → اختبار حساب النقاط
├── test_match_service.py       → اختبار تسجيل المباريات
├── test_league_service.py      → اختبار المواسم
├── test_cup.py                 → اختبار نظام الكأس
├── test_voting_live.py         → اختبار التصويت
├── test_api_admin.py           → اختبار API الإداري
├── test_api_public.py          → اختبار API العام
├── test_analytics_service.py   → اختبار التحليلات
└── test_repos.py               → اختبار الـ Repositories
```

### تشغيل الاختبارات:
```bash
pytest                          # جميع الاختبارات
pytest tests/test_points.py    # اختبار معين
pytest -v                      # وضع verbose
```

---

## 📊 الإحصائيات المتاحة

### على مستوى اللاعب:
- إحصائيات الموسم الحالي
- إحصائيات طوال المسيرة (All-Time)
- آخر موسم (للتراجع)
- معدل الفوز (Win Rate)
- مساهمة الأهداف في المباراة (GA/Match)
- الفورم (Hot 🔥 / Cold ❄️)

### على مستوى المباراة:
- النتيجة والإحصائيات التفصيلية لكل لاعب
- MVP (من التصويت)
- Captain
- Bonus Points

### على مستوى الدوري:
- Leaderboard
- Hall of Fame
- Cup Bracket
- Total matches في الموسم

---

## 🎨 الواجهة الأمامية (Frontend)

### التقنيات:
- **Vanilla JavaScript**: بدون أي framework
- **Chart.js**: للرسومات البيانية
- **CSS Custom Properties**: للثيمات
- **Font Awesome**: للأيقونات

### الملفات الرئيسية:
```
static/
├── css/style.css               → التنسيقات
└── js/
    ├── main.js                → الوظائف العامة
    ├── admin_dashboard.js     → لوحة التحكم
    ├── leaderboard.js         → جدول الترتيب
    ├── matches.js             → صفحة المباريات
    └── player_chart.js        → رسم بياني للاعب
```

---

## 🚀 النشر (Deployment)

### التطوير المحلي:
```bash
# 1. إعداد البيئة
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. تثبيت المتطلبات
pip install -r requirements.txt

# 3. تشغيل التطبيق
uvicorn app.main:app --reload

# 4. الوصول
http://127.0.0.1:8000
```

### الإنتاج (Render.com):
- ملف `render.yaml` جاهز
- يتطلب PostgreSQL Database
- متغيرات البيئة:
  ```
  DATABASE_URL=postgresql://...
  SECRET_KEY=...
  ```

---

## 🔄 سير العمل (Workflow)

### 1. إنشاء دوري جديد:
```
المستخدم → يملأ النموذج (اسم + slug + كلمة مرور)
         ↓
النظام → ينشئ League في قاعدة البيانات
         ↓
       يُعيد التوجيه إلى /l/{slug}
```

### 2. تسجيل مباراة:
```
المدير → يسجل دخول بكلمة المرور
        ↓
      يذهب إلى /l/{slug}/admin
        ↓
      يضيف بيانات المباراة + الإحصائيات
        ↓
MatchService → ينشئ Match + MatchStats
              يحدث إحصائيات اللاعبين
              يحسب النقاط (PointsCalculator)
              يحل مواجهات الكأس (CupService)
        ↓
      النظام يُحدث الـ Leaderboard
```

### 3. التصويت على MVP:
```
المدير → يفتح التصويت للمباراة
        ↓
اللاعبون → يصوّتون (3 جولات)
        ↓
النظام → يتحقق من الغش (IP + Fingerprint)
        يحفظ التصويت
        ↓
المدير → يغلق كل جولة
        ↓
النظام → يمنح نقاط إضافية للفائزين
```

### 4. إنهاء الموسم:
```
المدير → يضغط "End Season"
        ↓
LeagueService → يحفظ الفائز في Hall of Fame
                ينقل الإحصائيات إلى All-Time
                يعيد تعيين total_* إلى 0
                يحذف الكأس الحالي
        ↓
      موسم جديد يبدأ تلقائياً
```

---

## 📝 ملاحظات مهمة

### 1. **تطبيع الأسماء العربية**
في `match_service.py`:
```python
def normalize_name(name: str) -> str:
    # إزالة التشكيل
    # توحيد الألف (أ إ آ ا)
    # توحيد الياء (ى ي)
    # توحيد التاء المربوطة (ة ه)
```

### 2. **Migrations يدوية**
في `main.py` → `lifespan()`:
- يتم إضافة الأعمدة الجديدة تلقائياً عند بدء التطبيق
- آمنة: تتجاهل الأعمدة الموجودة مسبقاً

### 3. **حالات خاصة في الكأس**
- **Bye**: إذا كان عدد اللاعبين فردي، يتأهل أحدهم مباشرة
- **Co-op Final**: إذا لعب اللاعبان في نفس الفريق في النهائي = فوز مشترك

### 4. **حساب Clean Sheet للحارس**
- ≤2 أهداف مستقبلة = +10 نقاط
- 3-6 أهداف = +4 نقاط
- >6 أهداف = 0 نقطة

---

## 🔮 خطة المستقبل (من SAAS_PLAN.md)

### المرحلة الحالية:
✅ Multi-tenant architecture جاهزة
✅ Self-signup موجود
✅ JWT Auth مُطبق
✅ Slug-based routing

### مطلوب للتحول الكامل إلى SaaS:
❌ نظام المستخدمين (User Accounts)
❌ خطط الأسعار (Pricing Plans)
❌ فواتير (Billing)
❌ Super Admin Dashboard
❌ صفحة تسويقية محترفة

---

## 🛠️ نصائح للتطوير

### 1. إضافة ميزة جديدة:
```
1. أضف Model في models/models.py
2. أضف Schema في schemas/schemas.py
3. أضف Repository methods في repositories/
4. أضف Service logic في services/
5. أضف Routes في routers/
6. اكتب Tests في tests/
```

### 2. تعديل نظام النقاط:
```python
# في services/points.py:
# أضف Strategy جديد:
class MyCustomPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        # منطقك هنا
        return points
        
# أضفه للـ calculator:
self.strategies.append(MyCustomPoints())
```

### 3. إضافة شارة جديدة:
```python
# في services/achievements.py:
class MyBadge(BadgeRule):
    def evaluate(self, player, history):
        # شرط الحصول على الشارة
        if condition:
            return {
                "name": "اسم الشارة",
                "icon": "🏅",
                "description": "الوصف"
            }
        return None
```

---

## 📚 الموارد المفيدة

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy ORM**: https://docs.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/
- **Chart.js**: https://www.chartjs.org/

---

**تم التحديث في**: مارس 2026  
**الإصدار**: 3.0  
**الحالة**: في الإنتاج ✅

