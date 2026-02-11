"""Coin diameters (mm) and a free-text -> key mapper for contributor scale references."""
COINS_MM = {"us_quarter": 24.26, "us_penny": 19.05, "us_nickel": 21.21, "us_dime": 17.91, "eur_1": 23.25, "eur_2": 25.75, "eur_50c": 24.25,
            "gbp_1": 23.43, "gbp_2": 28.4, "gbp_10p": 24.5, "cad_quarter": 23.88, "aud_1": 25.0, "cny_1": 25.0, "jpy_100": 22.6}
def coin_key(text):
    t = (text or "").lower()
    if "cad" in t or "canad" in t: return "cad_quarter" if "quarter" in t else None
    table = [("quarter", "us_quarter"), ("penny", "us_penny"), ("nickel", "us_nickel"), ("dime", "us_dime"), ("2 euro", "eur_2"), ("2€", "eur_2"), ("1 euro", "eur_1"), ("1€", "eur_1"),
             ("50 cent", "eur_50c"), ("£2", "gbp_2"), ("2 pound", "gbp_2"), ("£1", "gbp_1"), ("1 pound", "gbp_1"), ("10p", "gbp_10p"), ("100 yen", "jpy_100"), ("1 yuan", "cny_1")]
    for k, v in table:
        if k in t: return v
    return None
