"""
Real OFAC sanctions-list crypto addresses. Unlike engine/fixtures.py's
KNOWN_EXCHANGE_WALLETS/KNOWN_MIXER_CONTRACTS (synthetic, seeded for a
reproducible offline demo), every address below is real - from the U.S.
Treasury OFAC Specially Designated Nationals (SDN) list, a public-domain
U.S. government dataset (17 U.S.C. section 105).

Source: OFAC SDN Advanced XML (treasury.gov/ofac/downloads/sanctions/1.0/
sdn_advanced.xml), via the "Digital Currency Address" feature type. Most
entries pulled from the machine-readable mirror at
github.com/cylon56/ofac-naughtylist (MIT/CC0, parsed directly from OFAC's
own export); a handful (Garantex's second ETH address, Vasinskyi, Li
Jiadong) were cross-checked directly against OFAC's recent-actions pages.

Snapshot pulled 2026-09, not a live daily sync - OFAC updates continuously.
A production deployment should re-pull the source XML on a schedule
instead of relying on a static file. This gives VAJRA a CONFIRMED
attribution tier resting on first-party government sanctions data rather
than a synthetic fixture. See engine/scoring.py's attribution_tier() for
how a hit here outranks a plain exchange-hot-wallet match - it names the
specific sanctions program, not just "known address".
"""

# (address, chain, entity_name, programs, date_listed) - programs is the
# OFAC sanctions-program code(s), shown verbatim in the UI so an officer
# or judge can look the citation up themselves.
SANCTIONED_ADDRESSES = [
    # --- Lazarus Group (DPRK state-linked hacking group) ---
    ("0x08723392Ed15743cc38513C4925f5e6be5c17243", "ETHEREUM", "Lazarus Group", ["DPRK3"], "2019-09-13"),
    ("0x098B716B8Aaf21512996dC57EB0615e2383E2f96", "ETHEREUM", "Lazarus Group", ["DPRK3"], "2019-09-13"),
    ("0x35fB6f6DB4fb05e6A4cE86f2C93691425626d4b1", "ETHEREUM", "Lazarus Group", ["DPRK3"], "2019-09-13"),
    ("0xa0e1c89Ef1a489c9C7dE96311eD5Ce5D32c20E4B", "ETHEREUM", "Lazarus Group", ["DPRK3"], "2019-09-13"),
    # --- Garantex Europe OU (Russia-linked exchange, laundering infra) ---
    ("0x57EC89A0C056163A0314e413320f9B3ABe761259", "ETHEREUM", "Garantex Europe OU", ["CYBER4", "RUSSIA-EO14024"], "2022-04-05"),
    ("0x7CEd75026204aC29C34bEA98905D4C949F27361e", "ETHEREUM", "Garantex Europe OU", ["CYBER4", "RUSSIA-EO14024"], "2022-04-05"),
    ("3E6ZCKRrsdPc35chA9Eftp1h3DLW18NFNV", "BITCOIN", "Garantex Europe OU", ["CYBER4", "RUSSIA-EO14024"], "2022-04-05"),
    # --- SUEX OTC, S.R.O. (crypto OTC desk, laundering for ransomware/fraud proceeds) ---
    ("0x19aa5fe80d33a56d56c78e82ea5e50e5d80b4dff", "ETHEREUM", "SUEX OTC, S.R.O.", ["CYBER2"], "2021-09-21"),
    ("1295rkVyNfFpqZpXvKGhDqwhP1jZcNNDMV", "BITCOIN", "SUEX OTC, S.R.O.", ["CYBER2"], "2021-09-21"),
    ("1CF46Rfbp97absrs7zb7dFfZS6qBXUm9EP", "BITCOIN", "SUEX OTC, S.R.O.", ["CYBER2"], "2021-09-21"),
    # --- CHATEX (crypto exchange, laundering infra, tied to SUEX) ---
    ("0x48549a34ae37b12f6a30566245176994e17c6b4a", "ETHEREUM", "CHATEX", ["CYBER2"], "2021-11-08"),
    ("32VgTk8kGvBsqkHhkvtNooGdtqZm46jTVo", "BITCOIN", "CHATEX", ["CYBER2"], "2021-11-08"),
    # --- Blender.io (Bitcoin mixer used to launder Axie Infinity/Lazarus proceeds) ---
    ("15PggTG7YhJKiE6B16vkKzA1YDTZipXEX4", "BITCOIN", "Blender.io", ["CYBER2"], "2022-05-06"),
    ("32DaxSzUhLBHY2WGSWQYiBSHnRsfQZrrRp", "BITCOIN", "Blender.io", ["CYBER2"], "2022-05-06"),
    # --- Hydra Market (largest darknet market, crypto laundering hub) ---
    ("123WBUDmSJv4GctdVEz6Qq6z8nXSKrJ4KX", "BITCOIN", "Hydra Market", ["CYBER2"], "2022-04-05"),
    ("12VrYZgS1nmf9KHHped24xBb1aLLRpV2cT", "BITCOIN", "Hydra Market", ["CYBER2"], "2022-04-05"),
    # --- Tornado Cash co-founder (mixer, DeFi laundering) ---
    ("0x43fa21d92141BA9db43052492E0DeEE5aa5f0A93", "ETHEREUM", "Semenov Roman", ["DPRK3"], "2023-08-23"),
    ("0x5a7a51bfb49f190e5a6060a5bc6052ac14a3b59f", "ETHEREUM", "Semenov Roman", ["DPRK3"], "2023-08-23"),
    # --- Garantex Europe OU: additional address from OFAC's own 2022-04-05
    # SDN update page (ofac.treasury.gov/recent-actions/20220405) ---
    ("0x7FF9cFad3877F21d41Da833E2F775dB0569eE3D9", "ETHEREUM", "Garantex Europe OU", ["CYBER4", "RUSSIA-EO14024"], "2022-04-05"),
    # --- Vasinskyi, Yaroslav (REvil ransomware affiliate - laundered ransom
    # payments through crypto; source: OFAC's 2021-11-08 SDN update) ---
    ("35QpLWYkvD3ALhjbge5bK2kd7HfHYcDMu3", "BITCOIN", "Vasinskyi, Yaroslav", ["CYBER2"], "2021-11-08"),
    ("3NQ1aa9ceirMJ1JvRq3eXefvXj1L639fzX", "BITCOIN", "Vasinskyi, Yaroslav", ["CYBER2"], "2021-11-08"),
    ("3BsyZ7qRFSi3NsaoV1Ff724qAgrEpjVUHm", "BITCOIN", "Vasinskyi, Yaroslav", ["CYBER2"], "2021-11-08"),
    # --- Li, Jiadong (DPRK-linked launderer of the 2018 exchange hack
    # proceeds attributed to Lazarus Group; source: OFAC's 2020-03-02
    # SDN update, ofac.treasury.gov/recent-actions/20200302) ---
    ("1EfMVkxQQuZfBdocpJu6RUsCJvenQWbQyE", "BITCOIN", "Li, Jiadong", ["DPRK3"], "2020-03-02"),
    ("17UVSMegvrzfobKC82dHXpZLtLcqzW9stF", "BITCOIN", "Li, Jiadong", ["DPRK3"], "2020-03-02"),
    ("39eboeqYNFe2VoLC3mUGx4dh6GNhLB3D2q", "BITCOIN", "Li, Jiadong", ["DPRK3"], "2020-03-02"),
    ("1JHdQHkBZiim1cb4hyUh2PbzEbbg6z2TrF", "BITCOIN", "Sinbad", ["CYBER2", "DPRK3"], "2023-11-29"),
    # --- Chen Zhi (2025 transnational crypto-fraud-compound designation - directly on-PS) ---
    ("35irs2AU6pVgenYbWvMRz22avDBLC9XMkd", "BITCOIN", "Chen Zhi", ["TCO"], "2025-10-14"),
    ("386sPhHBbLidzPnoxUH74jiiYkHYtobefQ", "BITCOIN", "Chen Zhi", ["TCO"], "2025-10-14"),
    # --- Wang Yunhe / 911 S5 botnet (fraud-proxy infrastructure) ---
    ("0xe1d865c3d669dcc8c57c8d023140cb204e672ee4", "ETHEREUM", "Wang Yunhe", ["CYBER2"], "2024-05-28"),
    ("1NaRX1GZgtZ7E8iXo8YUdTtnb8rAK5QFJa", "BITCOIN", "Wang Yunhe", ["CYBER2"], "2024-05-28"),
]

_BY_ADDRESS = {addr.lower(): {"address": addr, "chain": chain, "entity_name": name, "programs": programs, "date_listed": listed}
               for addr, chain, name, programs, listed in SANCTIONED_ADDRESSES}


def lookup(address):
    """Direct first-party match against the real OFAC SDN digital-currency
    address list. Returns None on no match - case-insensitive so an EVM
    checksum-cased address still matches (Bitcoin addresses are already
    case-sensitive by design and stored as OFAC published them)."""
    if not address:
        return None
    return _BY_ADDRESS.get(address.lower())
