"""Server-side Kiswahili/English texts.

Everything the platform *generates* for people (advice, alerts, profile factors, SMS)
comes from here. Helpers return a bilingual dict {"en": ..., "sw": ...} so stored records
can be shown in whichever language the viewer picks; SMS uses the recipient's preferred
language (User.language)."""

from typing import Any

SUPPORTED = ("sw", "en")
DEFAULT_LANGUAGE = "sw"

CROP_NAMES = {
    "maize": {"en": "maize", "sw": "mahindi"},
    "beans": {"en": "beans", "sw": "maharage"},
    "rice": {"en": "rice", "sw": "mchele"},
    "sorghum": {"en": "sorghum", "sw": "mtama"},
    "sunflower": {"en": "sunflower", "sw": "alizeti"},
}

MESSAGES: dict[str, dict[str, str]] = {
    # --- irrigation
    "irrigation.when.today_morning": {"en": "this morning", "sw": "leo asubuhi"},
    "irrigation.when.today_evening": {"en": "this evening", "sw": "leo jioni"},
    "irrigation.when.tomorrow_morning": {"en": "tomorrow morning", "sw": "kesho asubuhi"},
    "irrigation.when.none": {"en": "no irrigation needed now", "sw": "hakuna haja ya kumwagilia sasa"},
    "irrigation.headline.irrigate": {
        "en": "Irrigate {when}, about {mm} mm",
        "sw": "Mwagilia {when}, takriban mm {mm}",
    },
    "irrigation.headline.skip_rain": {
        "en": "Don't irrigate: rain is expected",
        "sw": "Usimwagilie: mvua inatarajiwa",
    },
    "irrigation.headline.no_action": {"en": "Soil moisture is fine", "sw": "Unyevu wa udongo ni mzuri"},
    "irrigation.headline.check_sensor": {
        "en": "No recent sensor data: check the sensor",
        "sw": "Hakuna data mpya ya kihisi: kagua kihisi",
    },
    "irrigation.reason.moisture_below": {
        "en": "Soil moisture is {moisture}%, below the {threshold}% refill level for {crop} at the {stage} stage",
        "sw": "Unyevu wa udongo ni {moisture}%, chini ya kiwango cha {threshold}% kinachohitajika kwa {crop} katika hatua ya {stage}",
    },
    "irrigation.reason.moisture_ok": {
        "en": "Soil moisture is {moisture}%, above the {threshold}% refill level",
        "sw": "Unyevu wa udongo ni {moisture}%, juu ya kiwango cha {threshold}%",
    },
    "irrigation.reason.no_rain": {
        "en": "Only {rain} mm of rain forecast in the next 2 days",
        "sw": "Mvua ya mm {rain} tu inatarajiwa ndani ya siku 2 zijazo",
    },
    "irrigation.reason.rain_expected": {
        "en": "{rain} mm of rain forecast in the next 2 days covers most of the {deficit} mm deficit",
        "sw": "Mvua ya mm {rain} inayotarajiwa ndani ya siku 2 itafidia sehemu kubwa ya upungufu wa mm {deficit}",
    },
    "irrigation.reason.high_et": {
        "en": "Crop water use is high today (ET₀ {et0} mm/day)",
        "sw": "Mahitaji ya maji ya mmea ni makubwa leo (ET₀ mm {et0} kwa siku)",
    },
    "irrigation.reason.hot": {
        "en": "Hot day ahead ({tmax}°C): irrigate early to reduce evaporation",
        "sw": "Siku ya joto kali ({tmax}°C): mwagilia mapema kupunguza uvukizaji",
    },
    "irrigation.reason.no_data": {
        "en": "The last soil reading is older than {hours} hours",
        "sw": "Kipimo cha mwisho cha udongo ni cha zaidi ya saa {hours} zilizopita",
    },
    "irrigation.reason.weather_simulated": {
        "en": "Weather forecast is simulated (offline demo)",
        "sw": "Utabiri wa hali ya hewa ni wa kuigwa (maonyesho bila mtandao)",
    },
    "stage.initial": {"en": "initial", "sw": "awali"},
    "stage.vegetative": {"en": "vegetative", "sw": "ukuaji"},
    "stage.flowering": {"en": "flowering", "sw": "maua"},
    "stage.maturity": {"en": "maturity", "sw": "kukomaa"},
    "stage.harvested": {"en": "harvested", "sw": "imevunwa"},
    # --- farm alerts
    "alert.dry_soil": {
        "en": "Very dry soil on {farm}: {moisture}% moisture",
        "sw": "Udongo mkavu sana shambani {farm}: unyevu {moisture}%",
    },
    "alert.heat": {"en": "Heat alert on {farm}: {temp}°C", "sw": "Tahadhari ya joto shambani {farm}: {temp}°C"},
    "alert.sensor_offline": {
        "en": "Sensor {device} has not reported for {hours} hours",
        "sw": "Kihisi {device} hakijatuma data kwa saa {hours}",
    },
    "alert.sensor_suspect": {
        "en": "Suspicious readings from sensor {device}: {detail}",
        "sw": "Vipimo vya kutiliwa shaka kutoka kihisi {device}: {detail}",
    },
    # --- spoilage
    "risk.LOW": {"en": "Low", "sw": "Chini"},
    "risk.MEDIUM": {"en": "Medium", "sw": "Wastani"},
    "risk.HIGH": {"en": "High", "sw": "Juu"},
    "spoilage.driver.rh_high": {
        "en": "Humidity averaged {rh}% (safe below {limit}%)",
        "sw": "Unyevu hewani wastani {rh}% (salama chini ya {limit}%)",
    },
    "spoilage.driver.rh_elevated": {
        "en": "Humidity is elevated at {rh}% (ideal below {limit}%)",
        "sw": "Unyevu hewani uko juu kidogo {rh}% (bora chini ya {limit}%)",
    },
    "spoilage.driver.hours_humid": {
        "en": "{hours} hours above {limit}% humidity in the last day",
        "sw": "Saa {hours} juu ya unyevu wa {limit}% katika siku iliyopita",
    },
    "spoilage.driver.temp_high": {
        "en": "Temperature reached {temp}°C (safe below {limit}°C)",
        "sw": "Joto limefika {temp}°C (salama chini ya {limit}°C)",
    },
    "spoilage.driver.rising": {
        "en": "Humidity is rising ({delta}+ points over the window)",
        "sw": "Unyevu hewani unaongezeka (alama {delta}+ katika kipindi)",
    },
    "spoilage.driver.long_storage": {
        "en": "Stored for {days} days: check the grain more often",
        "sw": "Imehifadhiwa kwa siku {days}: kagua nafaka mara kwa mara",
    },
    "spoilage.driver.safe": {
        "en": "Temperature and humidity are in the safe range",
        "sw": "Joto na unyevu viko katika kiwango salama",
    },
    "spoilage.driver.no_data": {
        "en": "No ghala sensor data yet",
        "sw": "Bado hakuna data ya kihisi cha ghala",
    },
    "spoilage.action.HIGH": {
        "en": "Ventilate the ghala today, check bags for moisture and mould, and move bags off the floor",
        "sw": "Fungua madirisha ya ghala leo kupitisha hewa, kagua magunia kama yana unyevu au ukungu, na nyanyua magunia kutoka sakafuni",
    },
    "spoilage.action.MEDIUM": {
        "en": "Improve airflow and re-check conditions within 24 hours",
        "sw": "Ongeza mzunguko wa hewa na kagua tena ndani ya saa 24",
    },
    "spoilage.action.LOW": {"en": "Keep monitoring; no action needed", "sw": "Endelea kufuatilia; hakuna hatua inayohitajika"},
    "alert.spoilage": {
        "en": "{level} spoilage risk for {batch} at {warehouse}. {action}",
        "sw": "Hatari ya kuharibika: {level} kwa {batch} ghalani {warehouse}. {action}",
    },
    # --- marketplace
    "alert.order_new": {
        "en": "New order from {buyer}: {qty} kg of {batch} at {price} TZS/kg",
        "sw": "Oda mpya kutoka {buyer}: kg {qty} za {batch} kwa TZS {price}/kg",
    },
    "alert.order_status": {
        "en": "Order #{order} is now {status}",
        "sw": "Oda #{order} sasa iko katika hali: {status}",
    },
    "alert.sale_confirmed": {
        "en": "Sale confirmed: {qty} kg for {amount} TZS. It is now part of your verified history",
        "sw": "Mauzo yamethibitishwa: kg {qty} kwa TZS {amount}. Sasa ni sehemu ya historia yako iliyothibitishwa",
    },
    "alert.receipt_issued": {
        "en": "Warehouse receipt {receipt} issued for {batch}: {qty} kg, grade {grade}",
        "sw": "Stakabadhi ya ghala {receipt} imetolewa kwa {batch}: kg {qty}, daraja {grade}",
    },
    # --- finance
    "alert.loan_submitted": {
        "en": "New loan application #{loan} for {amount} TZS",
        "sw": "Ombi jipya la mkopo #{loan} la TZS {amount}",
    },
    "alert.loan_decided": {
        "en": "Your loan application #{loan} was {status}. Reason from the lender: {reason}",
        "sw": "Ombi lako la mkopo #{loan} limekuwa {status}. Sababu ya mkopeshaji: {reason}",
    },
    "alert.claim_proposed": {
        "en": "Rainfall trigger met on policy #{policy}: a claim was proposed for insurer review",
        "sw": "Kigezo cha mvua kimefikiwa kwenye bima #{policy}: dai limependekezwa kwa ukaguzi wa bima",
    },
    "alert.claim_decided": {
        "en": "Claim #{claim} was {status}. Reason from the insurer: {reason}",
        "sw": "Dai #{claim} limekuwa {status}. Sababu ya kampuni ya bima: {reason}",
    },
    "alert.policy_status": {
        "en": "Insurance policy #{policy} ({product}) is now {status}",
        "sw": "Bima #{policy} ({product}) sasa iko katika hali: {status}",
    },
    "alert.claim_filed": {
        "en": "New claim #{claim} filed on policy #{policy}",
        "sw": "Dai jipya #{claim} limewasilishwa kwenye bima #{policy}",
    },
    "alert.consent_granted": {
        "en": "{farmer} shared their profile with you for: {purpose}",
        "sw": "{farmer} ameshiriki wasifu wake nawe kwa ajili ya: {purpose}",
    },
    # --- security
    "alert.locked": {
        "en": "Too many wrong PIN attempts. Your account is locked for {minutes} minutes",
        "sw": "Umekosea PIN mara nyingi. Akaunti yako imefungwa kwa dakika {minutes}",
    },
    "sms.otp": {
        "en": "Your Shambani-Kifedha code is {code}. It expires in 10 minutes. Never share it.",
        "sw": "Nambari yako ya Shambani-Kifedha ni {code}. Itaisha baada ya dakika 10. Usimpe mtu yeyote.",
    },
    # --- explainable profile
    "profile.pos.adherence": {
        "en": "Followed irrigation advice on {followed} of {total} recommendations",
        "sw": "Alifuata ushauri wa umwagiliaji mara {followed} kati ya {total}",
    },
    "profile.risk.adherence_low": {
        "en": "Followed irrigation advice on only {followed} of {total} recommendations",
        "sw": "Alifuata ushauri wa umwagiliaji mara {followed} tu kati ya {total}",
    },
    "profile.pos.storage_ok": {
        "en": "Ghala conditions stayed safe; no spoilage alerts left unresolved",
        "sw": "Hali ya ghala ilibaki salama; hakuna tahadhari ya kuharibika iliyoachwa bila kushughulikiwa",
    },
    "profile.risk.storage_alerts": {
        "en": "{count} high spoilage-risk alerts in storage",
        "sw": "Tahadhari {count} za hatari kubwa ya kuharibika ghalani",
    },
    "profile.pos.sales": {
        "en": "{sales} verified sales to {buyers} different buyers",
        "sw": "Mauzo {sales} yaliyothibitishwa kwa wanunuzi {buyers} tofauti",
    },
    "profile.risk.no_sales": {
        "en": "No verified sales yet",
        "sw": "Bado hakuna mauzo yaliyothibitishwa",
    },
    "profile.pos.receipts": {
        "en": "{count} digital warehouse receipts for {kg} kg stored in a verified ghala",
        "sw": "Stakabadhi {count} za ghala za kidijitali kwa kg {kg} zilizohifadhiwa katika ghala lililothibitishwa",
    },
    "profile.pos.cooperative": {
        "en": "Member of a cooperative ({name})",
        "sw": "Mwanachama wa ushirika ({name})",
    },
    "profile.risk.single_crop": {
        "en": "Single crop ({crop}): exposed to drought in this district",
        "sw": "Zao moja ({crop}): liko hatarini kwa ukame katika wilaya hii",
    },
    "profile.risk.drought_region": {
        "en": "{region} is a semi-arid, drought-prone region",
        "sw": "{region} ni eneo kame kiasi lenye hatari ya ukame",
    },
    "profile.risk.short_history": {
        "en": "Only {seasons} season of verified history so far",
        "sw": "Historia iliyothibitishwa ya msimu {seasons} tu hadi sasa",
    },
    "profile.pos.long_history": {
        "en": "{seasons} seasons of verified history",
        "sw": "Misimu {seasons} ya historia iliyothibitishwa",
    },
    "profile.product.input_loan": {
        "en": "Repayment can be timed to the {month} harvest sale",
        "sw": "Marejesho yanaweza kupangwa baada ya mauzo ya mavuno ya {month}",
    },
    "profile.product.weather_index_insurance": {
        "en": "Drought exposure is the main risk",
        "sw": "Hatari kuu ni ukame",
    },
    "profile.product.storage_cover": {
        "en": "Produce is stored in a ghala; cover against storage loss",
        "sw": "Mazao yamehifadhiwa ghalani; kinga dhidi ya hasara ya uhifadhi",
    },
    "profile.product.storage_backed_loan": {
        "en": "Future: an active warehouse receipt could back a loan (needs a regulated receipt system)",
        "sw": "Baadaye: stakabadhi hai ya ghala inaweza kudhamini mkopo (inahitaji mfumo rasmi wa stakabadhi)",
    },
    "profile.disclaimer": {
        "en": "Decision support only. The lender makes and is accountable for the credit decision.",
        "sw": "Ni msaada wa kufanya uamuzi tu. Mkopeshaji ndiye anayefanya na kuwajibika kwa uamuzi wa mkopo.",
    },
    # --- savings
    "savings.inputs": {"en": "Next-season inputs", "sw": "Pembejeo za msimu ujao"},
    "savings.emergency": {"en": "Emergency reserve", "sw": "Akiba ya dharura"},
    "savings.household": {"en": "Household / business needs", "sw": "Mahitaji ya nyumbani / biashara"},
    "savings.goal": {"en": "Savings goals", "sw": "Malengo ya akiba"},
    "savings.reason": {
        "en": "Split of {amount} TZS from your latest verified income. You can change it.",
        "sw": "Mgawanyo wa TZS {amount} kutoka mapato yako ya karibuni yaliyothibitishwa. Unaweza kuubadilisha.",
    },
    # --- insurance
    "insurance.rec.weather_index": {
        "en": "Weather-index (drought) cover for {crop}: pays if season rainfall falls below {mm} mm",
        "sw": "Bima ya kiashiria cha hali ya hewa (ukame) kwa {crop}: hulipa kama mvua ya msimu ni chini ya mm {mm}",
    },
    "insurance.rec.storage_cover": {
        "en": "Storage cover for {kg} kg in the ghala against spoilage and theft",
        "sw": "Bima ya uhifadhi kwa kg {kg} ghalani dhidi ya kuharibika na wizi",
    },
    "fraud.flatline": {"en": "flat-lined values", "sw": "thamani zisizobadilika"},
    "fraud.impossible": {"en": "physically impossible value {value}", "sw": "thamani isiyowezekana {value}"},
    "fraud.jump": {"en": "sudden jump of {delta}", "sw": "mruko wa ghafla wa {delta}"},
    "fraud.duplicate_batch": {
        "en": "Possible duplicate batch: {batch} matches {other} (same farmer, crop, date, quantity)",
        "sw": "Huenda ni kundi lililorudiwa: {batch} linafanana na {other} (mkulima, zao, tarehe na kiasi sawa)",
    },
    "fraud.qty_mismatch": {
        "en": "Quantity mismatch on {batch}: receipt {receipt_qty} kg vs batch {batch_qty} kg",
        "sw": "Kiasi hakilingani kwa {batch}: stakabadhi kg {receipt_qty} dhidi ya kundi kg {batch_qty}",
    },
}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _fmt(value: Any, lang: str) -> Any:
    if isinstance(value, dict) and set(value) >= {"en", "sw"}:
        return value[lang]
    if isinstance(value, float):
        return f"{value:,.1f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,}"
    return value


def t(key: str, lang: str = DEFAULT_LANGUAGE, **params: Any) -> str:
    template = MESSAGES[key][lang if lang in SUPPORTED else DEFAULT_LANGUAGE]
    return template.format_map(_SafeDict({k: _fmt(v, lang) for k, v in params.items()}))


def bi(key: str, **params: Any) -> dict[str, str]:
    """Bilingual text: {"en": ..., "sw": ...}. Params may themselves be bilingual dicts."""
    return {lang: t(key, lang, **params) for lang in SUPPORTED}


def crop_name(crop_type: str) -> dict[str, str]:
    return CROP_NAMES.get(crop_type, {"en": crop_type, "sw": crop_type})


def pick_language(user_language: str | None, requested: str | None = None) -> str:
    for candidate in (requested, user_language):
        if candidate:
            short = candidate.split(",")[0].split("-")[0].strip().lower()
            if short in SUPPORTED:
                return short
    return DEFAULT_LANGUAGE
