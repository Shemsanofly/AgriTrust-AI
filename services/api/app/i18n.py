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
    "ghala.act.rising": {
        "en": "Humidity will reach {rh}% in {hours} h. Act before then.",
        "sw": "Unyevu utafika {rh}% ndani ya saa {hours}. Chukua hatua mapema.",
    },
    "ghala.act.open_windows": {
        "en": "Open the windows now: outside air is drier ({outside}%).",
        "sw": "Fungua madirisha sasa: hewa ya nje ni kavu zaidi ({outside}%).",
    },
    "ghala.act.close_windows": {
        "en": "Keep windows closed: outside air is humid ({outside}%). Open on a dry afternoon.",
        "sw": "Funga madirisha: hewa ya nje ina unyevu ({outside}%). Fungua mchana wa jua.",
    },
    "ghala.act.ventilate": {"en": "Ventilate the ghala.", "sw": "Pitisha hewa ghalani."},
    "ghala.act.lift_bags": {
        "en": "Keep bags on pallets, off the walls; check for mould.",
        "sw": "Weka magunia juu ya chaga, mbali na ukuta; kagua ukungu.",
    },
    "ghala.act.cool_air": {
        "en": "Room is warm: open vents while outside is cooler ({outside}°C).",
        "sw": "Ghala lina joto: fungua matundu ya hewa nje kukiwa na ubaridi ({outside}°C).",
    },
    "ghala.act.night_air": {
        "en": "Room is warm: ventilate at night or early morning.",
        "sw": "Ghala lina joto: pitisha hewa usiku au alfajiri.",
    },
    "ghala.act.ok": {"en": "Conditions are safe. Keep windows as they are.", "sw": "Hali ni salama. Acha madirisha kama yalivyo."},
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
    "planting.limit.ph_low": {
        "en": "{crop} prefers pH {lo}-{hi}; your soil is {ph} — apply lime before planting.",
        "sw": "{crop} hupenda pH {lo}-{hi}; udongo wako ni {ph} — weka chokaa kabla ya kupanda.",
    },
    "planting.limit.ph_high": {
        "en": "{crop} prefers pH {lo}-{hi}; your soil is {ph} — add compost or manure.",
        "sw": "{crop} hupenda pH {lo}-{hi}; udongo wako ni {ph} — ongeza mboji au samadi.",
    },
    "planting.limit.salinity": {
        "en": "{crop} is sensitive to salty soil (EC {ec} dS/m) — expect lower yield.",
        "sw": "{crop} haivumilii chumvi ya udongo (EC {ec} dS/m) — mavuno yanaweza kupungua.",
    },
    "planting.limit.dry": {
        "en": "{crop} needs wet soil; moisture is only {moisture}% without irrigation.",
        "sw": "{crop} huhitaji udongo wenye maji; unyevu ni {moisture}% tu bila umwagiliaji.",
    },
    "planting.timing.plant_now": {
        "en": "Good time to plant: moisture {moisture}%, {rain} mm rain expected this week.",
        "sw": "Wakati mzuri wa kupanda: unyevu {moisture}%, mvua mm {rain} wiki hii.",
    },
    "planting.timing.irrigate_first": {
        "en": "Soil is dry ({moisture}%). Irrigate before planting.",
        "sw": "Udongo ni mkavu ({moisture}%). Mwagilia kabla ya kupanda.",
    },
    "planting.timing.plant_after_rain": {
        "en": "Soil is dry ({moisture}%). Plant after the next good rain ({rain} mm expected).",
        "sw": "Udongo ni mkavu ({moisture}%). Panda baada ya mvua nzuri ijayo (mm {rain} zinatarajiwa).",
    },
    "planting.timing.wait_for_rains": {
        "en": "Soil is dry ({moisture}%) and little rain is expected ({rain} mm). Wait for the rains.",
        "sw": "Udongo ni mkavu ({moisture}%) na mvua ni kidogo (mm {rain}). Subiri mvua zianze.",
    },
    "nutrient.N": {"en": "Nitrogen", "sw": "Naitrojeni"},
    "nutrient.P": {"en": "Phosphorus", "sw": "Fosforasi"},
    "nutrient.K": {"en": "Potassium", "sw": "Potasiamu"},
    "planting.irrigation.drip": {"en": "drip", "sw": "matone"},
    "planting.irrigation.furrow": {"en": "furrow", "sw": "mifereji"},
    "planting.irrigation.sprinkler": {"en": "sprinkler", "sw": "kinyunyizio"},
    # --- USSD menus (Kiswahili-first channel)
    "ussd.main.title": {"en": "Welcome to Shambani Kifedha", "sw": "Karibu Shambani Kifedha"},
    "ussd.main.farm": {"en": "My farm", "sw": "Shamba Langu"},
    "ussd.main.ghala": {"en": "Ghala (storage)", "sw": "Ghala"},
    "ussd.main.market": {"en": "Market", "sw": "Soko"},
    "ussd.main.finance": {"en": "Finance", "sw": "Fedha"},
    "ussd.main.exit": {"en": "Exit", "sw": "Toka"},
    "ussd.main.goodbye": {"en": "Thank you. Goodbye.", "sw": "Asante. Kwaheri."},
    "ussd.unregistered.title": {
        "en": "Welcome to Shambani Kifedha\n\nYour number is not registered.",
        "sw": "Karibu Shambani Kifedha\n\nNamba yako haijasajiliwa.",
    },
    "ussd.unregistered.register": {"en": "Register", "sw": "Jisajili"},
    "ussd.nav.back": {"en": "Back", "sw": "Rudi"},
    "ussd.nav.more": {"en": "More", "sw": "Zaidi"},
    "ussd.error.invalid": {"en": "Invalid choice. Try again.", "sw": "Chaguo si sahihi. Jaribu tena."},
    "ussd.error.unavailable": {
        "en": "Sorry, the service is unavailable. Try again later.",
        "sw": "Samahani, huduma haipatikani sasa. Jaribu tena baadaye.",
    },
    "ussd.error.phone": {"en": "Invalid phone number.", "sw": "Namba ya simu si sahihi."},
    "ussd.farm.title": {"en": "MY FARM", "sw": "SHAMBA LANGU"},
    "ussd.farm.crops_line": {"en": "Crops: {crops}", "sw": "Mazao: {crops}"},
    "ussd.farm.info_opt": {"en": "Farm info", "sw": "Taarifa za shamba"},
    "ussd.farm.conditions_opt": {"en": "Farm conditions (AI)", "sw": "Hali ya shamba (AI)"},
    "ussd.farm.planting_opt": {"en": "Best crop to plant (AI)", "sw": "Zao linalofaa (AI)"},
    "ussd.farm.add_crop_opt": {"en": "Add crop", "sw": "Ongeza zao"},
    "ussd.farm.irrigation_opt": {"en": "Irrigation advice", "sw": "Ushauri wa umwagiliaji"},
    "ussd.farm.crop_added": {
        "en": "{crop} ({acres} acres) added to your farm.",
        "sw": "Zao la {crop} (ekari {acres}) limeongezwa shambani kwako.",
    },
    "ussd.crop.acres": {
        "en": "How many acres of {crop}?\n(farm size: {max} acres)",
        "sw": "{crop} ni ekari ngapi?\n(ukubwa wa shamba: ekari {max})",
    },
    "ussd.farm.conditions": {
        "en": "FARM CONDITIONS ({region})\nTemperature: {temp}°C\nAir humidity: {rh}%\nSoil moisture: {moisture}\nSoil pH: {ph}\nSalinity: {salinity}\nBest crops: {crops}",
        "sw": "HALI YA SHAMBA ({region})\nJoto: {temp}°C\nUnyevu wa hewa: {rh}%\nUnyevu wa udongo: {moisture}\npH ya udongo: {ph}\nChumvi: {salinity}\nMazao bora: {crops}",
    },
    "ussd.farm.info": {
        "en": "MY FARM\n\nArea: {region}\nSize: {acres} acres\nSoil: {soil}\nCrops: {crops}",
        "sw": "SHAMBA LANGU\n\nEneo: {region}\nUkubwa: {acres} acres\nUdongo: {soil}\nMazao: {crops}",
    },
    "ussd.farm.none": {"en": "No farm registered yet.", "sw": "Hakuna shamba lililosajiliwa bado."},
    "ussd.farm.no_crops": {"en": "none yet", "sw": "hakuna bado"},
    "ussd.stage.initial": {"en": "just planted", "sw": "mwanzo"},
    "ussd.stage.vegetative": {"en": "growing", "sw": "ukuaji"},
    "ussd.stage.flowering": {"en": "flowering", "sw": "maua"},
    "ussd.stage.maturity": {"en": "mature", "sw": "kukomaa"},
    "ussd.stage.harvested": {"en": "harvested", "sw": "mavuno"},
    "ussd.ph.acidic": {"en": "acidic", "sw": "tindikali"},
    "ussd.ph.slightly_acidic": {"en": "slightly acidic", "sw": "tindikali kidogo"},
    "ussd.ph.neutral": {"en": "neutral", "sw": "wastani"},
    "ussd.ph.alkaline": {"en": "alkaline", "sw": "alkali"},
    "ussd.salinity.low": {"en": "low", "sw": "chini"},
    "ussd.salinity.moderate": {"en": "moderate", "sw": "wastani"},
    "ussd.salinity.high": {"en": "high", "sw": "juu"},
    "ussd.soil.low": {"en": "LOW", "sw": "CHINI"},
    "ussd.soil.ok": {"en": "OK", "sw": "SAWA"},
    "ussd.soil.high": {"en": "HIGH", "sw": "JUU"},
    "ussd.plant.advice": {
        "en": "PLANTING ADVICE\nBest crops: {best}\n{avoid}{timing}",
        "sw": "USHAURI WA KUPANDA\nMazao bora: {best}\n{avoid}{timing}",
    },
    "ussd.plant.avoid": {"en": "Avoid: {crops}", "sw": "Epuka: {crops}"},
    "ussd.advice.none": {"en": "No advice available yet.", "sw": "Hakuna ushauri bado."},
    "ussd.advice.current": {"en": "IRRIGATION\n\n{text}", "sw": "UMWAGILIAJI\n\n{text}"},
    "ussd.ghala.title": {"en": "GHALA", "sw": "GHALA"},
    "ussd.ghala.outlook_opt": {"en": "Ghala conditions (AI)", "sw": "Hali ya ghala (AI)"},
    "ussd.ghala.stock_opt": {"en": "My stored crops", "sw": "Mazao yangu ghalani"},
    "ussd.ghala.alerts_opt": {"en": "Ghala alerts", "sw": "Tahadhari za ghala"},
    "ussd.ghala.summary": {"en": "In storage: {kg} kg ({count})", "sw": "Ghalani: kg {kg} ({count})"},
    "ussd.ghala.none_short": {"en": "Nothing in storage yet", "sw": "Hakuna mazao ghalani bado"},
    "ussd.ghala.none": {
        "en": "You have no crops in a ghala yet. Record your harvest on the web app.",
        "sw": "Bado huna mazao ghalani. Rekodi mavuno yako kwenye tovuti.",
    },
    "ussd.ghala.no_readings": {"en": "No sensor readings from {ghala} yet.", "sw": "Bado hakuna vipimo kutoka {ghala}."},
    "ussd.ghala.outlook": {
        "en": "{ghala}\nNow: {temp}°C, humidity {rh}%\nIn {hours} h: {temp_pred}°C, {rh_pred}%\nRisk: {risk}\n{action}",
        "sw": "{ghala}\nSasa: {temp}°C, unyevu {rh}%\nBaada ya saa {hours}: {temp_pred}°C, {rh_pred}%\nHatari: {risk}\n{action}",
    },
    "ussd.ghala.stock_title": {"en": "STORED CROPS", "sw": "MAZAO GHALANI"},
    "ussd.risk.HIGH": {"en": "HIGH", "sw": "JUU"},
    "ussd.risk.MEDIUM": {"en": "MEDIUM", "sw": "WASTANI"},
    "ussd.risk.LOW": {"en": "safe", "sw": "salama"},
    "ussd.risk.UNKNOWN": {"en": "no data", "sw": "hakuna data"},
    "ussd.finance.title": {"en": "FINANCE", "sw": "FEDHA"},
    "ussd.finance.loans_opt": {"en": "Loans", "sw": "Mikopo"},
    "ussd.finance.savings_opt": {"en": "Savings", "sw": "Akiba"},
    "ussd.finance.insurance_opt": {"en": "Insurance & disasters", "sw": "Bima na majanga"},
    "ussd.finance.profile_opt": {"en": "My finance status", "sw": "Hali yangu ya fedha"},
    "ussd.finance.why_opt": {"en": "Why this status", "sw": "Sababu"},
    "ussd.finance.band_low": {"en": "STRONG", "sw": "NZURI"},
    "ussd.finance.band_medium": {"en": "AVERAGE", "sw": "WASTANI"},
    "ussd.finance.band_high": {"en": "NEEDS WORK", "sw": "INAHITAJI JUHUDI"},
    "ussd.finance.profile": {
        "en": "YOUR STATUS\n\nSeason income:\n{income}\n\nSales:\n{sales}\n\nStatus:\n{band}",
        "sw": "HALI YAKO\n\nMapato ya msimu:\n{income}\n\nMauzo:\n{sales}\n\nHali:\n{band}",
    },
    "ussd.finance.no_sales": {"en": "No verified sales yet.", "sw": "Hakuna mauzo yaliyothibitishwa bado."},
    "ussd.finance.why_none": {"en": "No explanation available.", "sw": "Hakuna maelezo bado."},
    "ussd.finance.why_title": {"en": "REASONS", "sw": "SABABU"},
    "ussd.alerts.none": {"en": "No open alerts.", "sw": "Hakuna tahadhari wazi."},
    "ussd.pin.wrong": {"en": "Wrong PIN. Nothing was sent.", "sw": "PIN si sahihi. Hakuna kilichotumwa."},
    "ussd.loan.title": {"en": "LOANS", "sw": "MIKOPO"},
    "ussd.loan.apply_opt": {"en": "Request a loan", "sw": "Omba mkopo"},
    "ussd.loan.status_opt": {"en": "My loans", "sw": "Mikopo yangu"},
    "ussd.loan.amount": {"en": "Enter loan amount (TZS):", "sw": "Weka kiasi cha mkopo (TZS):"},
    "ussd.loan.amount_suggested": {
        "en": "Suggested up to {amount}.\nEnter loan amount (TZS):",
        "sw": "Kiwango kinachopendekezwa hadi {amount}.\nWeka kiasi cha mkopo (TZS):",
    },
    "ussd.loan.purpose_title": {"en": "Loan purpose:", "sw": "Mkopo ni kwa ajili ya:"},
    "ussd.loan.purpose.inputs": {"en": "Seeds & fertiliser", "sw": "Mbegu na mbolea"},
    "ussd.loan.purpose.storage": {"en": "Ghala storage", "sw": "Kuhifadhi ghalani"},
    "ussd.loan.purpose.equipment": {"en": "Equipment / irrigation", "sw": "Vifaa / umwagiliaji"},
    "ussd.loan.purpose.other": {"en": "Other farm needs", "sw": "Mahitaji mengine ya shamba"},
    "ussd.loan.confirm_pin": {
        "en": "Loan {amount} for {purpose}.\nEnter your PIN to send:",
        "sw": "Mkopo {amount} kwa {purpose}.\nWeka PIN yako kutuma:",
    },
    "ussd.loan.sent": {
        "en": "Loan request #{id} for {amount} sent to {lender}. You will get an SMS with the decision.",
        "sw": "Ombi la mkopo #{id} la {amount} limetumwa kwa {lender}. Utapata SMS ya uamuzi.",
    },
    "ussd.loan.no_lender": {"en": "No lender is available right now.", "sw": "Hakuna mkopeshaji kwa sasa."},
    "ussd.loan.none": {"en": "You have no loan requests.", "sw": "Huna maombi ya mkopo."},
    "ussd.loan.list_title": {"en": "MY LOANS", "sw": "MIKOPO YANGU"},
    "ussd.savings.menu_title": {"en": "SAVINGS", "sw": "AKIBA"},
    "ussd.savings.view_opt": {"en": "My savings", "sw": "Akiba yangu"},
    "ussd.savings.deposit_opt": {"en": "Add savings", "sw": "Weka akiba"},
    "ussd.savings.new_opt": {"en": "New savings goal", "sw": "Lengo jipya la akiba"},
    "ussd.savings.none": {"en": "You have no savings goals yet.", "sw": "Bado huna malengo ya akiba."},
    "ussd.savings.title": {"en": "MY SAVINGS: {total}", "sw": "AKIBA YANGU: {total}"},
    "ussd.savings.pick_goal": {"en": "Save towards:", "sw": "Weka akiba kwa:"},
    "ussd.savings.deposit_amount": {"en": "Amount to add to {goal} (TZS):", "sw": "Kiasi cha kuweka kwenye {goal} (TZS):"},
    "ussd.savings.deposited": {
        "en": "{amount} added to {goal}. Saved: {saved}/{target}.",
        "sw": "{amount} imewekwa kwenye {goal}. Akiba: {saved}/{target}.",
    },
    "ussd.savings.bucket_title": {"en": "Goal type:", "sw": "Aina ya lengo:"},
    "ussd.savings.target": {"en": "Target amount for {bucket} (TZS):", "sw": "Kiasi lengwa cha {bucket} (TZS):"},
    "ussd.savings.created": {"en": "Goal '{goal}' created: target {target}.", "sw": "Lengo '{goal}' limewekwa: {target}."},
    "ussd.ins.title": {"en": "INSURANCE", "sw": "BIMA"},
    "ussd.ins.report_opt": {"en": "Report a disaster", "sw": "Ripoti janga"},
    "ussd.ins.mine_opt": {"en": "My cover & claims", "sw": "Bima na madai yangu"},
    "ussd.ins.request_opt": {"en": "Request cover", "sw": "Omba bima"},
    "ussd.ins.request_title": {"en": "Choose cover:", "sw": "Chagua bima:"},
    "ussd.ins.option": {"en": "{n}. {product}: cover {cover}, fee {premium}", "sw": "{n}. {product}: kinga {cover}, ada {premium}"},
    "ussd.ins.no_options": {
        "en": "No cover to suggest yet. Add a crop or store a harvest first.",
        "sw": "Hakuna bima ya kupendekeza bado. Ongeza zao au hifadhi mavuno kwanza.",
    },
    "ussd.ins.confirm_pin": {"en": "{product}, fee {premium}.\nEnter your PIN to request:", "sw": "{product}, ada {premium}.\nWeka PIN yako kuomba:"},
    "ussd.ins.sent": {
        "en": "Cover request #{id} sent to {insurer}. It starts once they approve.",
        "sw": "Ombi la bima #{id} limetumwa kwa {insurer}. Itaanza baada ya kuidhinishwa.",
    },
    "ussd.ins.no_insurer": {"en": "No insurer is available right now.", "sw": "Hakuna kampuni ya bima kwa sasa."},
    "ussd.ins.none": {"en": "You have no insurance cover yet.", "sw": "Bado huna bima."},
    "ussd.ins.list_title": {"en": "MY COVER", "sw": "BIMA ZANGU"},
    "ussd.ins.claim": {"en": "Claim #{id}", "sw": "Dai #{id}"},
    "ussd.product.weather_index": {"en": "Rainfall cover", "sw": "Bima ya mvua"},
    "ussd.product.storage_cover": {"en": "Ghala cover", "sw": "Bima ya ghala"},
    "ussd.disaster.title": {"en": "What happened?", "sw": "Nini kimetokea?"},
    "ussd.disaster.drought": {"en": "Drought", "sw": "Ukame"},
    "ussd.disaster.flood": {"en": "Flood", "sw": "Mafuriko"},
    "ussd.disaster.pests": {"en": "Pests / disease", "sw": "Wadudu / magonjwa"},
    "ussd.disaster.hail_wind": {"en": "Hail / strong wind", "sw": "Mvua ya mawe / upepo"},
    "ussd.disaster.storage_loss": {"en": "Loss in the ghala", "sw": "Hasara ghalani"},
    "ussd.disaster.no_policy": {
        "en": "You have no active cover for this loss. Choose 'Request cover' first.",
        "sw": "Huna bima hai inayolinda hasara hii. Chagua 'Omba bima' kwanza.",
    },
    "ussd.disaster.confirm": {
        "en": "Report {disaster} under cover #{policy} ({product})?\n1. Yes\n0. No",
        "sw": "Ripoti {disaster} kwa bima #{policy} ({product})?\n1. Ndiyo\n0. Hapana",
    },
    "ussd.disaster.sent": {
        "en": "Report sent as claim #{id}. The insurer will review it and you will get an SMS.",
        "sw": "Ripoti imetumwa kama dai #{id}. Bima itakagua na utapata SMS.",
    },
    "ussd.status.SUBMITTED": {"en": "submitted", "sw": "limetumwa"},
    "ussd.status.UNDER_REVIEW": {"en": "under review", "sw": "linakaguliwa"},
    "ussd.status.APPROVED": {"en": "approved", "sw": "limeidhinishwa"},
    "ussd.status.DECLINED": {"en": "declined", "sw": "limekataliwa"},
    "ussd.status.DISBURSED": {"en": "paid out", "sw": "limetolewa"},
    "ussd.status.REPAYING": {"en": "repaying", "sw": "linalipwa"},
    "ussd.status.CLOSED": {"en": "closed", "sw": "limefungwa"},
    "ussd.status.REQUESTED": {"en": "requested", "sw": "imeombwa"},
    "ussd.status.ACTIVE": {"en": "active", "sw": "hai"},
    "ussd.status.EXPIRED": {"en": "expired", "sw": "imeisha"},
    "ussd.status.FILED": {"en": "filed", "sw": "limewasilishwa"},
    "ussd.status.EVIDENCE_ATTACHED": {"en": "evidence attached", "sw": "ushahidi umeambatishwa"},
    "ussd.status.REJECTED": {"en": "rejected", "sw": "limekataliwa"},
    "ussd.status.PAID": {"en": "paid", "sw": "limelipwa"},
    "ussd.market.title": {"en": "MARKET", "sw": "SOKO"},
    "ussd.market.stock_opt": {"en": "My crops for sale", "sw": "Mazao yangu sokoni"},
    "ussd.market.sales_opt": {"en": "Sales history", "sw": "Historia ya mauzo"},
    "ussd.market.sales_title": {"en": "SALES: {total} ({count})", "sw": "MAUZO: {total} ({count})"},
    "ussd.market.prices_opt": {"en": "Market prices", "sw": "Bei ya soko"},
    "ussd.market.requests_opt": {"en": "Buyer requests", "sw": "Maombi ya wanunuzi"},
    "ussd.market.no_stock": {"en": "No crops listed for sale.", "sw": "Hakuna mazao yaliyoorodheshwa sokoni."},
    "ussd.market.stock_title": {"en": "FOR SALE", "sw": "SOKONI"},
    "ussd.market.prices_none": {"en": "No price data yet.", "sw": "Hakuna bei bado."},
    "ussd.market.prices_title": {"en": "PRICES", "sw": "BEI"},
    "ussd.market.no_requests": {"en": "No buyer requests.", "sw": "Hakuna maombi ya wanunuzi."},
    "ussd.market.requests_title": {"en": "BUYER REQUESTS", "sw": "MAOMBI YA WANUNUZI"},
    "ussd.reg.name": {"en": "REGISTER\n\nEnter your name:", "sw": "JISAJILI\n\nWeka jina lako:"},
    "ussd.reg.region": {"en": "Choose your farm's region:", "sw": "Chagua mkoa wa shamba lako:"},
    "ussd.reg.size": {"en": "Enter farm size in acres:", "sw": "Weka ukubwa wa shamba\nkwa acres:"},
    "ussd.reg.crop_title": {"en": "Choose crop:", "sw": "Chagua zao:"},
    "ussd.reg.crop.maize": {"en": "Maize", "sw": "Mahindi"},
    "ussd.reg.crop.rice": {"en": "Rice", "sw": "Mpunga"},
    "ussd.reg.crop.sunflower": {"en": "Sunflower", "sw": "Alizeti"},
    "ussd.reg.crop.beans": {"en": "Beans", "sw": "Maharage"},
    "ussd.reg.crop.sorghum": {"en": "Sorghum", "sw": "Mtama"},
    "ussd.reg.crop.none": {"en": "Not planted yet", "sw": "Sijapanda bado"},
    "ussd.reg.done": {
        "en": "Registration complete!\n{region}: {temp}°C, humidity {rh}%, soil moisture {moisture}%, pH {ph}.\nBest crops: {crops}.\nPIN sent by SMS.",
        "sw": "Usajili umekamilika!\n{region}: {temp}°C, unyevu wa hewa {rh}%, udongo {moisture}%, pH {ph}.\nMazao bora: {crops}.\nPIN imetumwa kwa SMS.",
    },
    "ussd.reg.pin_sms": {
        "en": "SHAMBANI KIFEDHA: Your web login PIN is {pin}. Keep it private.",
        "sw": "SHAMBANI KIFEDHA: PIN yako ya kuingia mtandaoni ni {pin}. Iweke siri.",
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
