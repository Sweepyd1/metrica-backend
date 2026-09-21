# Блок-лист зарубежных почтовых провайдеров. Всё остальное (включая
# российские корпоративные/учебные домены вроде edu.hse.ru) разрешено.
BLOCKED_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "yahoo.co.uk",
        "icloud.com",
        "me.com",
        "mac.com",
        "protonmail.com",
        "proton.me",
        "aol.com",
        "gmx.com",
        "zoho.com",
        "qq.com",
        "163.com",
    }
)


def is_blocked_email_domain(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain in BLOCKED_EMAIL_DOMAINS
