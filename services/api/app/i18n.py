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
        "en": "Soil is getting dry, but about {rain} mm of rain is expected {when}. Delay irrigation.",
        "sw": "Udongo unakauka, lakini mvua ya takriban mm {rain} inatarajiwa {when}. Subiri kumwagilia.",
    },
    "irrigation.rain_when.today": {"en": "today", "sw": "leo"},
    "irrigation.rain_when.tomorrow": {"en": "tomorrow", "sw": "kesho"},
    "irrigation.rain_when.two_days": {"en": "in the next two days", "sw": "ndani ya siku mbili"},
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
        "en": "{rain} mm of rain is forecast in the next 2 days: most of the ~{mm} mm you would apply",
        "sw": "Mvua ya mm {rain} inatarajiwa ndani ya siku 2: sehemu kubwa ya mm ~{mm} ambazo ungemwagilia",
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
    "spoilage.headline.HIGH_RISING": {
        "en": "Humidity is rising. Open the ghala windows today.",
        "sw": "Unyevu unapanda. Fungua madirisha ya ghala leo.",
    },
    "spoilage.headline.HIGH": {
        "en": "Storage conditions are unsafe. Act today.",
        "sw": "Hali ya ghala si salama. Chukua hatua leo.",
    },
    "spoilage.headline.MEDIUM": {
        "en": "Conditions are drifting. Check the ghala within 24 hours.",
        "sw": "Hali inabadilika. Kagua ghala ndani ya saa 24.",
    },
    "spoilage.headline.LOW": {
        "en": "Storage conditions are safe.",
        "sw": "Hali ya uhifadhi ni salama.",
    },
    "spoilage.headline.UNKNOWN": {
        "en": "No ghala readings yet.",
        "sw": "Bado hakuna vipimo vya ghala.",
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
    "alert.contract_offered": {
        "en": "{buyer} offers to buy {qty} kg of {crop} at {price} TZS/kg, delivery {month}",
        "sw": "{buyer} anataka kununua kg {qty} za {crop} kwa TZS {price}/kg, kupelekwa {month}",
    },
    "alert.contract_accepted": {
        "en": "{farmer} accepted your contract #{contract} for {qty} kg of {crop}",
        "sw": "{farmer} amekubali mkataba wako #{contract} wa kg {qty} za {crop}",
    },
    "alert.contract_declined": {
        "en": "{farmer} declined your contract #{contract} for {qty} kg of {crop}",
        "sw": "{farmer} amekataa mkataba wako #{contract} wa kg {qty} za {crop}",
    },
    "alert.contract_cancelled": {
        "en": "{buyer} withdrew the contract offer #{contract}",
        "sw": "{buyer} ameondoa ofa ya mkataba #{contract}",
    },
    "alert.contract_fulfilled": {
        "en": "Contract #{contract} with {buyer} is marked delivered",
        "sw": "Mkataba #{contract} na {buyer} umewekwa kuwa umetekelezwa",
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
    "alert.new_device": {
        "en": "New sign-in to your account from {device}. If this was not you, change your PIN and sign out other devices.",
        "sw": "Umeingia kwenye akaunti yako kutoka kifaa kipya ({device}). Kama si wewe, badilisha PIN na toa vifaa vingine.",
    },
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
        "en": "Digital warehouse receipts: {count}, for {kg} kg stored in a verified ghala",
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
    # --- credit assessment: the five criteria and their findings
    "credit.c.transactions": {"en": "Transaction history", "sw": "Historia ya miamala"},
    "credit.c.farm": {"en": "Farm size and location", "sw": "Ukubwa na eneo la shamba"},
    "credit.c.production": {"en": "Production history", "sw": "Historia ya uzalishaji"},
    "credit.c.offtake": {"en": "Off-take contracts", "sw": "Mikataba ya ununuzi wa mavuno"},
    "credit.c.condition": {"en": "Farm condition (IoT/AI)", "sw": "Hali ya shamba (IoT/AI)"},
    "credit.tx.sales": {
        "en": "Verified sales: {sales} · {amount} TZS · buyers: {buyers}",
        "sw": "Mauzo {sales} yaliyothibitishwa yenye thamani ya TZS {amount} kwa wanunuzi {buyers} tofauti",
    },
    "credit.tx.no_sales": {"en": "No verified sales yet", "sw": "Bado hakuna mauzo yaliyothibitishwa"},
    "credit.tx.repaid": {"en": "Loans repaid in full: {count}", "sw": "Mikopo {count} imelipwa kikamilifu"},
    "credit.tx.repaying": {"en": "Loans being repaid now: {count}", "sw": "Mikopo {count} inaendelea kulipwa"},
    "credit.tx.savings": {
        "en": "Savings: {amount} TZS (goals: {goals})",
        "sw": "TZS {amount} zimewekwa akiba katika malengo {goals}",
    },
    "credit.tx.no_savings": {"en": "No savings recorded yet", "sw": "Bado hakuna akiba iliyorekodiwa"},
    "credit.farm.size": {
        "en": "Farm area: {acres} acres (farms: {farms}) · about {kg} kg a season, worth around {value} TZS",
        "sw": "Ekari {acres} kwenye mashamba {farms}: takriban kg {kg} kwa msimu, zenye thamani ya karibu TZS {value}",
    },
    "credit.farm.small": {
        "en": "Less than 1 acre limits how much the farm can produce",
        "sw": "Chini ya ekari 1 hupunguza kiasi shamba linachoweza kuzalisha",
    },
    "credit.farm.no_farm": {"en": "No farm registered yet", "sw": "Bado hakuna shamba lililosajiliwa"},
    "credit.farm.good_zone": {
        "en": "{region} has no major climate risk for farming",
        "sw": "{region} haina hatari kubwa ya hali ya hewa kwa kilimo",
    },
    "credit.farm.drought_irrigated": {
        "en": "{region} is drought-prone, but irrigation reduces the risk",
        "sw": "{region} ina hatari ya ukame, lakini umwagiliaji unapunguza hatari",
    },
    "credit.farm.drought_rainfed": {
        "en": "{region} is drought-prone and the farm depends on rain",
        "sw": "{region} ina hatari ya ukame na shamba linategemea mvua",
    },
    "credit.prod.none": {"en": "No harvests recorded yet", "sw": "Bado hakuna mavuno yaliyorekodiwa"},
    "credit.prod.seasons": {
        "en": "Seasons recorded: {seasons} · harvested in total: {kg} kg",
        "sw": "Misimu {seasons} imerekodiwa, jumla ya kg {kg} zimevunwa",
    },
    "credit.prod.consistent": {
        "en": "Harvests are steady from season to season",
        "sw": "Mavuno ni thabiti msimu hadi msimu",
    },
    "credit.prod.variable": {
        "en": "Harvests change a lot between seasons",
        "sw": "Mavuno yanabadilika sana kati ya misimu",
    },
    "credit.prod.short": {
        "en": "Only one season of records so far ({kg} kg harvested)",
        "sw": "Rekodi za msimu mmoja tu hadi sasa (kg {kg} zimevunwa)",
    },
    "credit.off.none": {
        "en": "No off-take contract with a buyer yet",
        "sw": "Bado hakuna mkataba wa ununuzi na mnunuzi",
    },
    "credit.off.active": {
        "en": "Accepted contracts: {count} (buyers: {buyers}) · {kg} kg worth {value} TZS",
        "sw": "Mikataba {count} iliyokubaliwa na wanunuzi {buyers} kwa kg {kg}, yenye thamani ya TZS {value}",
    },
    "credit.off.coverage": {
        "en": "Contracts cover {pct}% of the expected harvest",
        "sw": "Mikataba inashughulikia {pct}% ya mavuno yanayotarajiwa",
    },
    "credit.off.low_coverage": {
        "en": "Contracts cover only {pct}% of the expected harvest",
        "sw": "Mikataba inashughulikia {pct}% tu ya mavuno yanayotarajiwa",
    },
    "credit.off.fulfilled": {
        "en": "Earlier contracts delivered: {count}",
        "sw": "Mikataba {count} ya awali imetekelezwa",
    },
    "credit.cond.moisture_ok": {
        "en": "Soil moisture {value}% is in the healthy range ({source})",
        "sw": "Unyevu wa udongo {value}% uko katika kiwango kizuri ({source})",
    },
    "credit.cond.moisture_low": {
        "en": "Soil moisture {value}% is below the healthy range ({source})",
        "sw": "Unyevu wa udongo {value}% uko chini ya kiwango kizuri ({source})",
    },
    "credit.cond.moisture_high": {
        "en": "Soil moisture {value}% is above the healthy range ({source})",
        "sw": "Unyevu wa udongo {value}% uko juu ya kiwango kizuri ({source})",
    },
    "credit.cond.ph_ok": {
        "en": "Soil pH {value} suits most crops",
        "sw": "pH ya udongo {value} inafaa mazao mengi",
    },
    "credit.cond.ph_bad": {
        "en": "Soil pH {value} is outside the 5.5–7.5 range most crops need",
        "sw": "pH ya udongo {value} iko nje ya kiwango cha 5.5–7.5 kinachohitajika na mazao mengi",
    },
    "credit.cond.temp_ok": {
        "en": "Soil temperature {value}°C is suitable ({source})",
        "sw": "Joto la udongo {value}°C linafaa ({source})",
    },
    "credit.cond.temp_bad": {
        "en": "Soil temperature {value}°C stresses crops ({source})",
        "sw": "Joto la udongo {value}°C linasumbua mazao ({source})",
    },
    "credit.cond.salinity_ok": {
        "en": "Salinity {value} dS/m: not saline ({source})",
        "sw": "Chumvi {value} dS/m: si udongo wa chumvi ({source})",
    },
    "credit.cond.salinity_mid": {
        "en": "Salinity {value} dS/m: slightly saline, sensitive crops may suffer ({source})",
        "sw": "Chumvi {value} dS/m: chumvi kidogo, mazao nyeti yanaweza kuathirika ({source})",
    },
    "credit.cond.salinity_high": {
        "en": "Salinity {value} dS/m: saline soil lowers yields ({source})",
        "sw": "Chumvi {value} dS/m: udongo wa chumvi hupunguza mavuno ({source})",
    },
    "credit.cond.no_data": {
        "en": "No soil readings or estimates yet",
        "sw": "Bado hakuna vipimo au makadirio ya udongo",
    },
    "credit.src.sensor": {"en": "sensor", "sw": "kihisi"},
    "credit.src.estimate": {"en": "AI estimate", "sw": "makadirio ya AI"},
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
    # --- planting advice (soil → crop)
    "planting.soil.loam": {"en": "loam", "sw": "tifutifu"},
    "planting.soil.sandy loam": {"en": "sandy loam", "sw": "tifutifu yenye mchanga"},
    "planting.soil.sandy": {"en": "sandy soil", "sw": "udongo wa mchanga"},
    "planting.soil.clay": {"en": "clay", "sw": "mfinyanzi"},
    "planting.fit.excellent": {"en": "Excellent", "sw": "Bora sana"},
    "planting.fit.good": {"en": "Good", "sw": "Nzuri"},
    "planting.fit.fair": {"en": "Fair", "sw": "Wastani"},
    "planting.fit.poor": {"en": "Poor", "sw": "Dhaifu"},
    "planting.headline": {
        "en": "On {soil} soil, prioritise {crops}",
        "sw": "Kwenye udongo wa {soil}, weka kipaumbele kwa {crops}",
    },
    "planting.summary.loam": {
        "en": "Loam holds nutrients and moisture well — suitable for most food crops.",
        "sw": "Udongo wa tifutifu huhifadhi virutubisho na unyevu vizuri — unafaa mazao mengi ya chakula.",
    },
    "planting.summary.sandy loam": {
        "en": "Sandy loam drains quickly and warms early — good for deep-rooted and drought-tolerant crops.",
        "sw": "Tifutifu yenye mchanga hutoa maji haraka na hupata joto mapema — inafaa mazao yenye mizizi mirefu na yanayostahimili ukame.",
    },
    "planting.summary.sandy": {
        "en": "Sandy soil drains fast and holds few nutrients — favour hardy crops and add organic matter.",
        "sw": "Udongo wa mchanga hutoa maji haraka na huhifadhi virutubisho vichache — chagua mazao thabiti na ongeza mbolea ya asili.",
    },
    "planting.summary.clay": {
        "en": "Clay holds water and nutrients but can be heavy — strong for rice and many cereals if managed well.",
        "sw": "Mfinyanzi hushikilia maji na virutubisho lakini unaweza kuwa mzito — unafaa mchele na nafaka nyingi ukisimamiwa vizuri.",
    },
    "planting.reason.excellent": {
        "en": "{crop} thrives on {soil} soil with typical smallholder practices.",
        "sw": "{crop} hukua vizuri sana kwenye udongo wa {soil} kwa mbinu za kawaida za mkulima mdogo.",
    },
    "planting.reason.good": {
        "en": "{crop} performs well on {soil} soil when planting and fertility are managed carefully.",
        "sw": "{crop} hufanya vizuri kwenye udongo wa {soil} ukipanda na kutunza rutuba kwa uangalifu.",
    },
    "planting.reason.fair": {
        "en": "{crop} can grow on {soil} soil but may need extra water, manure or drainage.",
        "sw": "{crop} linaweza kukua kwenye udongo wa {soil} lakini linaweza kuhitaji maji, mbolea au mifereji ya ziada.",
    },
    "planting.reason.poor": {
        "en": "{crop} is a poor match for {soil} soil — choose a better-suited crop if you can.",
        "sw": "{crop} halifai sana kwa udongo wa {soil} — chagua zao linalofaa zaidi ikiwezekana.",
    },
    "planting.current.excellent": {
        "en": "Your current {crop} is an excellent match for this {soil} soil.",
        "sw": "Zao lako la sasa ({crop}) linafaa sana kwa udongo huu wa {soil}.",
    },
    "planting.current.good": {
        "en": "Your current {crop} is a good match for this {soil} soil.",
        "sw": "Zao lako la sasa ({crop}) linafaa kwa udongo huu wa {soil}.",
    },
    "planting.current.fair": {
        "en": "Your current {crop} is only a fair match for {soil} soil — watch water and fertility closely.",
        "sw": "Zao lako la sasa ({crop}) linafaa kwa wastani tu kwa udongo wa {soil} — fuatilia maji na rutuba kwa karibu.",
    },
    "planting.current.poor": {
        "en": "Your current {crop} is a poor match for {soil} soil — consider a better-suited crop next season.",
        "sw": "Zao lako la sasa ({crop}) halifai sana kwa udongo wa {soil} — fikiria zao linalofaa zaidi msimu ujao.",
    },
    "planting.tip.loam": {
        "en": "Keep organic matter high with compost or manure so loam stays crumbly and fertile.",
        "sw": "Dumisha mbolea ya asili (compost au samadi) ili tifutifu ibaki laini na yenye rutuba.",
    },
    "planting.tip.sandy loam": {
        "en": "Mulch after planting to slow moisture loss on sandy loam.",
        "sw": "Funika udongo baada ya kupanda ili kupunguza upotevu wa unyevu kwenye tifutifu yenye mchanga.",
    },
    "planting.tip.sandy": {
        "en": "Add manure or compost each season; sandy soils need frequent light fertility inputs.",
        "sw": "Ongeza samadi au compost kila msimu; udongo wa mchanga unahitaji rutuba mara kwa mara.",
    },
    "planting.tip.clay": {
        "en": "Avoid working clay when it is wet; raise beds or ridges to improve drainage for upland crops.",
        "sw": "Usilime mfinyanzi ukiwa na maji mengi; tumia matuta kuboresha mifereji kwa mazao yasiyo ya maji.",
    },
    "planting.tip.general": {
        "en": "Match planting date to the local rains and use certified seed where possible.",
        "sw": "Linganisha tarehe ya kupanda na mvua za eneo lako na tumia mbegu bora inapowezekana.",
    },
    "planting.tip.rainfed": {
        "en": "You are rain-fed: prefer drought-tolerant crops and plant with the onset of reliable rains.",
        "sw": "Unategemea mvua: chagua mazao yanayostahimili ukame na panda mvua za kuaminika zinapoanza.",
    },
    "planting.tip.irrigated": {
        "en": "With {method} irrigation you can widen crop choice, but still match crops to soil drainage.",
        "sw": "Kwa umwagiliaji wa {method} unaweza kuchagua mazao mengi zaidi, lakini bado linganisha na mifereji ya udongo.",
    },
    "planting.ph.acidic": {
        "en": "Soil pH {ph} is acidic: apply agricultural lime before planting; most crops will struggle.",
        "sw": "pH ya udongo {ph} ni tindikali: weka chokaa ya kilimo kabla ya kupanda; mazao mengi yatatatizika.",
    },
    "planting.ph.slightly_acidic": {
        "en": "Soil pH {ph} is slightly acidic: well suited to maize, beans and sunflower.",
        "sw": "pH ya udongo {ph} ina tindikali kidogo: inafaa sana mahindi, maharage na alizeti.",
    },
    "planting.ph.neutral": {
        "en": "Soil pH {ph} is neutral: suitable for most food crops.",
        "sw": "pH ya udongo {ph} haina tindikali wala alkali: inafaa mazao mengi ya chakula.",
    },
    "planting.ph.alkaline": {
        "en": "Soil pH {ph} is alkaline: sorghum tolerates it best; add organic matter.",
        "sw": "pH ya udongo {ph} ni alkali: mtama huvumilia vizuri zaidi; ongeza mbolea ya asili.",
    },
    "planting.nutrient.low": {
        "en": "{nutrient} is low: plan a fertiliser top-up (ask your extension officer for the rate).",
        "sw": "{nutrient} iko chini: panga kuongeza mbolea (muulize afisa ugani kiwango sahihi).",
    },
    "nutrient.N": {"en": "Nitrogen", "sw": "Naitrojeni"},
    "nutrient.P": {"en": "Phosphorus", "sw": "Fosforasi"},
    "nutrient.K": {"en": "Potassium", "sw": "Potasiamu"},
    "planting.irrigation.drip": {"en": "drip", "sw": "matone"},
    "planting.irrigation.furrow": {"en": "furrow", "sw": "mifereji"},
    "planting.irrigation.sprinkler": {"en": "sprinkler", "sw": "kinyunyizio"},
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
