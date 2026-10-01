from datetime import date

SEED = 42
N_CLIENTS = 5000
FIRST_CLIENT_ID = 1001
PERIOD_START = date(2024, 9, 1)
PERIOD_END = date(2026, 8, 31)
HISTORY_START = date(2015, 1, 1)

TARGET_ANNUAL_CHURN = 0.125
SHARE_NEW_IN_PERIOD = 0.28
EXISTING_TENURE_MEAN_DAYS = 900
CHUNK_CLIENTS = 500

PROPERTY_TYPES = {
    "hotel":       {"share": 0.25, "rooms": (35, 0.60, 10, 300), "occ": 0.62, "adr": 5500, "los": 2.2, "risk": -0.15, "nature": False, "label": "Отель"},
    "mini_hotel":  {"share": 0.22, "rooms": (12, 0.35, 5, 30),   "occ": 0.58, "adr": 4200, "los": 2.0, "risk": 0.00,  "nature": False, "label": "Мини-отель"},
    "guest_house": {"share": 0.14, "rooms": (8, 0.40, 3, 20),    "occ": 0.50, "adr": 3200, "los": 2.8, "risk": 0.10,  "nature": False, "label": "Гостевой дом"},
    "apartments":  {"share": 0.14, "rooms": (10, 0.80, 1, 120),  "occ": 0.60, "adr": 4000, "los": 3.0, "risk": 0.30,  "nature": False, "label": "Апартаменты"},
    "hostel":      {"share": 0.08, "rooms": (15, 0.40, 5, 60),   "occ": 0.65, "adr": 1200, "los": 2.5, "risk": 0.20,  "nature": False, "label": "Хостел"},
    "glamping":    {"share": 0.08, "rooms": (8, 0.45, 3, 30),    "occ": 0.55, "adr": 8000, "los": 2.3, "risk": 0.25,  "nature": True,  "label": "Глэмпинг"},
    "resort_base": {"share": 0.09, "rooms": (25, 0.50, 8, 120),  "occ": 0.50, "adr": 4500, "los": 3.2, "risk": 0.05,  "nature": True,  "label": "База отдыха"},
}

REGIONS = {
    "Москва":                   {"w": 0.13, "kind": "city",   "price": 1.35},
    "Санкт-Петербург":          {"w": 0.12, "kind": "city",   "price": 1.20},
    "Московская область":       {"w": 0.07, "kind": "nature", "price": 1.10},
    "Краснодарский край":       {"w": 0.12, "kind": "sea",    "price": 1.15},
    "Республика Крым":          {"w": 0.06, "kind": "sea",    "price": 1.00},
    "Калининградская область":  {"w": 0.04, "kind": "sea",    "price": 1.00},
    "Ленинградская область":    {"w": 0.03, "kind": "nature", "price": 0.95},
    "Республика Карелия":       {"w": 0.04, "kind": "nature", "price": 1.00},
    "Республика Алтай":         {"w": 0.04, "kind": "nature", "price": 1.00},
    "Алтайский край":           {"w": 0.03, "kind": "nature", "price": 0.85},
    "Республика Татарстан":     {"w": 0.04, "kind": "city",   "price": 1.00},
    "Свердловская область":     {"w": 0.03, "kind": "city",   "price": 0.95},
    "Нижегородская область":    {"w": 0.03, "kind": "city",   "price": 0.90},
    "Ярославская область":      {"w": 0.03, "kind": "city",   "price": 0.90},
    "Новосибирская область":    {"w": 0.03, "kind": "city",   "price": 0.90},
    "Ставропольский край":      {"w": 0.03, "kind": "nature", "price": 0.95},
    "Республика Дагестан":      {"w": 0.03, "kind": "sea",    "price": 0.85},
    "Приморский край":          {"w": 0.03, "kind": "sea",    "price": 1.00},
    "Другие регионы":           {"w": 0.08, "kind": "city",   "price": 0.85},
}

SEASON_MONTHLY = {
    "city":   [0.80, 0.85, 0.90, 0.95, 1.00, 1.10, 1.15, 1.15, 1.00, 0.95, 0.90, 1.00],
    "sea":    [0.45, 0.45, 0.55, 0.70, 0.95, 1.40, 1.70, 1.75, 1.20, 0.75, 0.50, 0.60],
    "nature": [0.40, 0.30, 0.35, 0.55, 0.95, 1.50, 1.80, 1.80, 1.20, 0.65, 0.35, 0.55],
}
ACTIVITY_SEASON_DAMP = 0.7
WEEKDAY_FACTOR = [1.0, 1.0, 1.0, 1.0, 1.0, 0.75, 0.65]

ACQUISITION = {
    "sales":     {"w": 0.30, "risk": 0.00},
    "website":   {"w": 0.25, "risk": 0.20},
    "partner":   {"w": 0.15, "risk": 0.10},
    "referral":  {"w": 0.15, "risk": -0.20},
    "migration": {"w": 0.15, "risk": -0.10},
}
ACCOUNT_MANAGER_RISK = -0.35

MODULES = {
    "pms":              {"p": 1.00},
    "channel_manager":  {"p": 0.85},
    "booking_engine":   {"p": 0.55},
    "kassa":            {"p": 0.40},
    "payments":         {"p": 0.45, "requires": "booking_engine"},
    "price_monitoring": {"p": 0.20},
    "rms":              {"p": 0.10},
}
MODULE_RISK_PER_EXTRA = -0.15
MODULE_UPSELL_PROB = 0.15

TARIFFS = {
    "start":    {"price": 250.0, "risk": 0.20},
    "standard": {"price": 420.0, "risk": 0.00},
    "pro":      {"price": 650.0, "risk": -0.20},
}
TARIFF_ORDER = ["start", "standard", "pro"]
BILLING = {
    "month":   {"w": 0.70, "months": 1,  "discount": 0.00, "risk": 0.00},
    "quarter": {"w": 0.10, "months": 3,  "discount": 0.05, "risk": -0.15},
    "year":    {"w": 0.20, "months": 12, "discount": 0.12, "risk": -0.50},
}
MIN_MONTHLY_BILL = 1900.0
DUE_DAYS = 10

TENURE_RISK = [(6, 0.9), (12, 0.5), (24, 0.15)]
SEASONAL_AUTUMN_RISK = 0.2
LATENT_RISK_SIGMA = 0.45

CHURN_KINDS = {
    "gradual": {"w": 0.72, "window": (30, 90), "depth": (0.10, 0.45)},
    "sudden":  {"w": 0.28, "window": (0, 14),  "depth": (0.70, 1.00)},
}
CANCEL_REASONS = {
    "gradual": {"non_payment": 0.30, "switched_competitor": 0.25, "price": 0.15, "functionality": 0.15, "property_closed": 0.15},
    "sudden":  {"property_closed": 0.35, "sold_property": 0.35, "switched_competitor": 0.20, "non_payment": 0.10},
}
GRADUAL_LATE_PAY_PROB = 0.70
GRADUAL_MODULE_DROP_PROB = 0.50
GRADUAL_DOWNGRADE_PROB = 0.20
GRADUAL_TICKET_SPIKE = (2.5, 4.0)
CANCELLATION_TICKET_PROB = 0.45

DIP_PROB = 0.10
DIP_DAYS = (20, 60)
DIP_DEPTH = (0.30, 0.60)
DIP_TICKET_SPIKE = (1.5, 2.5)
HABITUAL_LATE_PAYER_PROB = 0.08
RANDOM_MODULE_DROP_PROB = 0.06
UPGRADE_PROB = 0.08

BOOKING_SOURCES = {
    "direct_widget": {"alpha": 2.0, "cancel": 0.10},
    "ota_ostrovok":  {"alpha": 2.5, "cancel": 0.18},
    "ota_yandex":    {"alpha": 2.0, "cancel": 0.16},
    "ota_avito":     {"alpha": 1.0, "cancel": 0.15},
    "ota_other":     {"alpha": 1.0, "cancel": 0.18},
    "phone":         {"alpha": 1.5, "cancel": 0.08},
}

TICKET_CATEGORIES = {
    "normal":     {"training": 0.18, "bug": 0.20, "cm_sync": 0.20, "billing": 0.14, "feature_request": 0.18, "other": 0.10},
    "onboarding": {"training": 0.50, "bug": 0.15, "cm_sync": 0.15, "billing": 0.10, "feature_request": 0.05, "other": 0.05},
    "risk":       {"training": 0.05, "bug": 0.27, "cm_sync": 0.22, "billing": 0.30, "feature_request": 0.06, "other": 0.10},
}
TICKET_PRIORITY = {"normal": [0.40, 0.45, 0.15], "risk": [0.25, 0.45, 0.30]}
TICKET_CHANNELS = {"chat": 0.55, "phone": 0.25, "email": 0.20}
CSAT = {"normal": [0.02, 0.03, 0.10, 0.25, 0.60], "risk": [0.12, 0.15, 0.25, 0.25, 0.23]}
PAYMENT_METHODS = {"bank_transfer": 0.75, "card": 0.20, "sbp": 0.05}

NAME_WORDS = [
    "Сосны", "Берег", "Уют", "Север", "Волна", "Причал", "Кедр", "Тайга", "Альпина", "Ривьера",
    "Панорама", "Старый город", "Невский", "Маяк", "Лесная сказка", "Озёрный", "Горизонт", "Бриз",
    "Пихта", "Бухта", "Метрополь", "Арбат", "Эльбрус", "Снежный", "Ладога", "Онего", "Катунь",
    "Династия", "Крона", "Тишина", "Полянка", "Солнечный", "Купол", "Европа", "Классик", "Лофт",
]
