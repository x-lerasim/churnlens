"""Параметры синтетического генератора отельной SaaS-платформы."""
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class GenConfig:
    n_clients: int = 5000
    start: date = date(2024, 1, 1)      # начало истории
    n_months: int = 36                  # 3 года
    seed: int = 42

    share_existing: float = 0.6         # доля клиентов, подключённых до начала истории
    max_prior_tenure_m: int = 60        # максимальный стаж «старых» клиентов на старте

    # Уход: logit(p_month) = churn_alpha - churn_beta * h + поправки
    churn_alpha: float = -4.6
    churn_beta: float = 1.0
    onboarding_months: int = 3
    onboarding_bump: float = 0.6
    january_price_bump: float = 0.35    # индексация тарифов в январе
    offseason_bump: float = 0.6         # курорты / юг в октябре-ноябре

    # Латентное «здоровье» клиента: AR(1) вокруг базового уровня
    h_phi: float = 0.85
    h_sigma: float = 0.30
    shock_prob: float = 0.01            # редкий негативный шок (конкурент, смена управляющего)
    shock_size: float = -1.2

    # Сигналы перед уходом
    silent_churn_share: float = 0.2     # уходят без предвестников
    precursor: tuple = field(default=(0.45, 0.65, 0.82, 0.93))  # множитель активности: месяц ухода, -1, -2, -3

    # Справочники
    hotel_types: dict = field(default_factory=lambda: {
        "hotel": 0.45, "mini_hotel": 0.25, "hostel": 0.12, "apartments": 0.10, "resort": 0.08})
    regions: dict = field(default_factory=lambda: {
        "moscow": 0.22, "spb": 0.15, "black_sea": 0.15, "regions_big": 0.28, "regions_other": 0.20})
    tariffs: tuple = ("start", "standard", "pro")
    churn_reasons: dict = field(default_factory=lambda: {
        "price": 0.25, "competitor": 0.25, "functionality": 0.15,
        "support": 0.10, "closed_business": 0.15, "other": 0.10})
