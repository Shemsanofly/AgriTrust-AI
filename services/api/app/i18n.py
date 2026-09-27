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
    "alert.payment_failed": {
        "en": "Payment for order #{order} did not go through ({reason}). You can try again.",
        "sw": "Malipo ya oda #{order} hayajafanikiwa ({reason}). Unaweza kujaribu tena.",
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
    # --- credit assessment criteria, off-take contracts
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
    "credit.c.transactions": {
        "en": "Transaction history",
        "sw": "Historia ya miamala",
    },
    "credit.c.farm": {
        "en": "Farm size and location",
        "sw": "Ukubwa na eneo la shamba",
    },
    "credit.c.production": {
        "en": "Production history",
        "sw": "Historia ya uzalishaji",
    },
    "credit.c.offtake": {
        "en": "Off-take contracts",
        "sw": "Mikataba ya ununuzi wa mavuno",
    },
    "credit.c.condition": {
        "en": "Farm condition (IoT/AI)",
        "sw": "Hali ya shamba (IoT/AI)",
    },
    "credit.tx.sales": {
        "en": "Verified sales: {sales} · {amount} TZS · buyers: {buyers}",
        "sw": "Mauzo {sales} yaliyothibitishwa yenye thamani ya TZS {amount} kwa wanunuzi {buyers} tofauti",
    },
    "credit.tx.no_sales": {
        "en": "No verified sales yet",
        "sw": "Bado hakuna mauzo yaliyothibitishwa",
    },
    "credit.tx.repaid": {
        "en": "Loans repaid in full: {count}",
        "sw": "Mikopo {count} imelipwa kikamilifu",
    },
    "credit.tx.repaying": {
        "en": "Loans being repaid now: {count}",
        "sw": "Mikopo {count} inaendelea kulipwa",
    },
    "credit.tx.savings": {
        "en": "Savings: {amount} TZS (goals: {goals})",
        "sw": "TZS {amount} zimewekwa akiba katika malengo {goals}",
    },
    "credit.tx.no_savings": {
        "en": "No savings recorded yet",
        "sw": "Bado hakuna akiba iliyorekodiwa",
    },
    "credit.farm.size": {
        "en": "Farm area: {acres} acres (farms: {farms}) · about {kg} kg a season, worth around {value} TZS",
        "sw": "Ekari {acres} kwenye mashamba {farms}: takriban kg {kg} kwa msimu, zenye thamani ya karibu TZS {value}",
    },
    "credit.farm.small": {
        "en": "Less than 1 acre limits how much the farm can produce",
        "sw": "Chini ya ekari 1 hupunguza kiasi shamba linachoweza kuzalisha",
    },
    "credit.farm.no_farm": {
        "en": "No farm registered yet",
        "sw": "Bado hakuna shamba lililosajiliwa",
    },
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
    "credit.prod.none": {
        "en": "No harvests recorded yet",
        "sw": "Bado hakuna mavuno yaliyorekodiwa",
    },
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
    # --- AI loan eligibility: feature labels and tips
    "ai.f.sales_count": {
        "en": "Verified sales: {v}",
        "sw": "Mauzo yaliyothibitishwa: {v}",
    },
    "ai.f.sales_income": {
        "en": "Verified income: TZS {v}",
        "sw": "Mapato yaliyothibitishwa: TZS {v}",
    },
    "ai.f.distinct_buyers": {
        "en": "Different buyers: {v}",
        "sw": "Wanunuzi tofauti: {v}",
    },
    "ai.f.selling_months": {
        "en": "Months with sales: {v}",
        "sw": "Miezi yenye mauzo: {v}",
    },
    "ai.f.savings": {
        "en": "Savings: TZS {v}",
        "sw": "Akiba: TZS {v}",
    },
    "ai.f.loans_repaid": {
        "en": "Loans repaid: {v}",
        "sw": "Mikopo iliyolipwa: {v}",
    },
    "ai.f.loans_open": {
        "en": "Loans still being repaid: {v}",
        "sw": "Mikopo inayoendelea kulipwa: {v}",
    },
    "ai.f.seasons": {
        "en": "Seasons recorded: {v}",
        "sw": "Misimu iliyorekodiwa: {v}",
    },
    "ai.f.harvest_kg": {
        "en": "Total harvested: {v} kg",
        "sw": "Jumla ya mavuno: kg {v}",
    },
    "ai.f.harvest_consistency": {
        "en": "Harvest steadiness: {v}",
        "sw": "Uthabiti wa mavuno: {v}",
    },
    "ai.f.ghala_receipts": {
        "en": "Ghala receipts: {v}",
        "sw": "Stakabadhi za ghala: {v}",
    },
    "ai.f.storage_alerts": {
        "en": "Unresolved spoilage alerts: {v}",
        "sw": "Tahadhari za kuharibika zisizoshughulikiwa: {v}",
    },
    "ai.f.advice_follow_rate": {
        "en": "Irrigation advice followed: {v}",
        "sw": "Ushauri wa umwagiliaji uliofuatwa: {v}",
    },
    "ai.f.acres": {
        "en": "Farm size: {v} acres",
        "sw": "Ukubwa wa shamba: ekari {v}",
    },
    "ai.f.drought_rainfed_1": {
        "en": "Rain-fed farm in a drought-prone region",
        "sw": "Shamba linalotegemea mvua katika eneo la ukame",
    },
    "ai.f.drought_rainfed_0": {
        "en": "Irrigated or low drought risk",
        "sw": "Linamwagiliwa au hatari ndogo ya ukame",
    },
    "ai.f.offtake_coverage": {
        "en": "Harvest covered by buyer contracts: {v}",
        "sw": "Mavuno yenye mikataba ya wanunuzi: {v}",
    },
    "ai.f.soil_condition": {
        "en": "Soil condition: {v}/100",
        "sw": "Hali ya udongo: {v}/100",
    },
    "ai.f.account_age": {
        "en": "Track record: {v} days",
        "sw": "Rekodi ya shughuli: siku {v}",
    },
    "ai.f.activity_90d": {
        "en": "Activities in the last 90 days: {v}",
        "sw": "Shughuli katika siku 90 zilizopita: {v}",
    },
    "ai.f.coming_harvest_1": {
        "en": "A harvest is coming to repay from",
        "sw": "Mavuno yanakuja ya kulipia mkopo",
    },
    "ai.f.coming_harvest_0": {
        "en": "No coming harvest recorded",
        "sw": "Hakuna mavuno yajayo yaliyorekodiwa",
    },
    "ai.tip.sales_count": {
        "en": "Sell through the Market so each sale is verified.",
        "sw": "Uza kupitia Soko ili kila mauzo yathibitishwe.",
    },
    "ai.tip.sales_income": {
        "en": "Sell more of your harvest through the platform.",
        "sw": "Uza zaidi ya mavuno yako kupitia jukwaa.",
    },
    "ai.tip.distinct_buyers": {
        "en": "Sell to more than one buyer.",
        "sw": "Uza kwa zaidi ya mnunuzi mmoja.",
    },
    "ai.tip.selling_months": {
        "en": "Sell regularly rather than all at once.",
        "sw": "Uza mara kwa mara badala ya mara moja tu.",
    },
    "ai.tip.savings": {
        "en": "Put some money in a savings goal.",
        "sw": "Weka pesa kidogo kwenye lengo la akiba.",
    },
    "ai.tip.loans_repaid": {
        "en": "Repaying a small loan on time builds your record.",
        "sw": "Kulipa mkopo mdogo kwa wakati hujenga rekodi yako.",
    },
    "ai.tip.loans_open": {
        "en": "Finish repaying your current loan first.",
        "sw": "Maliza kulipa mkopo wako wa sasa kwanza.",
    },
    "ai.tip.seasons": {
        "en": "Record every season's harvest.",
        "sw": "Rekodi mavuno ya kila msimu.",
    },
    "ai.tip.harvest_kg": {
        "en": "Record all of your harvests.",
        "sw": "Rekodi mavuno yako yote.",
    },
    "ai.tip.harvest_consistency": {
        "en": "Steadier harvests help: follow the planting and irrigation advice.",
        "sw": "Mavuno thabiti husaidia: fuata ushauri wa kupanda na kumwagilia.",
    },
    "ai.tip.ghala_receipts": {
        "en": "Store your harvest in a verified ghala.",
        "sw": "Hifadhi mavuno yako katika ghala lililothibitishwa.",
    },
    "ai.tip.storage_alerts": {
        "en": "Deal with the spoilage alerts on your stored crop.",
        "sw": "Shughulikia tahadhari za kuharibika kwa mazao yaliyohifadhiwa.",
    },
    "ai.tip.advice_follow_rate": {
        "en": "Follow the irrigation advice and mark it as done.",
        "sw": "Fuata ushauri wa umwagiliaji na uweke alama umefanya.",
    },
    "ai.tip.acres": {
        "en": "Register all the land you farm.",
        "sw": "Sajili ardhi yote unayolima.",
    },
    "ai.tip.drought_rainfed": {
        "en": "Irrigation or weather-index insurance lowers drought risk.",
        "sw": "Umwagiliaji au bima ya hali ya hewa hupunguza hatari ya ukame.",
    },
    "ai.tip.offtake_coverage": {
        "en": "Accept a buyer's contract for your coming harvest.",
        "sw": "Kubali mkataba wa mnunuzi kwa mavuno yako yajayo.",
    },
    "ai.tip.soil_condition": {
        "en": "Improve the soil (pH, moisture); follow the soil advice.",
        "sw": "Boresha udongo (pH, unyevu); fuata ushauri wa udongo.",
    },
    "ai.tip.account_age": {
        "en": "Your track record grows as you keep recording farm activity.",
        "sw": "Rekodi yako hukua kadiri unavyoendelea kurekodi shughuli za shamba.",
    },
    "ai.tip.activity_90d": {
        "en": "Keep your farm, harvests and sales up to date.",
        "sw": "Sasisha shamba, mavuno na mauzo yako mara kwa mara.",
    },
    "ai.tip.coming_harvest": {
        "en": "Add your crop with its expected harvest date.",
        "sw": "Ongeza zao lako pamoja na tarehe ya mavuno inayotarajiwa.",
    },
    "profile.product.input_loan_sales": {
        "en": "Sized to your verified sales of the past year",
        "sw": "Kulingana na mauzo yako yaliyothibitishwa ya mwaka uliopita",
    },
    # --- disaster forecast (drought, fire, flood)
    "hazard.why.water_balance": {
        "en": "Next 16 days: {rain} mm of rain expected, while crops lose about {et0} mm to heat and wind",
        "sw": "Siku 16 zijazo: mvua ya mm {rain} inatarajiwa, huku mazao yakipoteza takriban mm {et0} kwa joto na upepo",
    },
    "hazard.why.dry_season": {
        "en": "These dates are normally dry here ({normal} mm on average in the last 10 years)",
        "sw": "Tarehe hizi kwa kawaida ni kavu hapa (wastani wa mm {normal} katika miaka 10 iliyopita)",
    },
    "hazard.why.vs_normal": {
        "en": "Rain forecast is {pct}% of the normal {normal} mm for these dates",
        "sw": "Mvua inayotabiriwa ni {pct}% ya kawaida ya mm {normal} kwa tarehe hizi",
    },
    "hazard.why.soil": {
        "en": "Soil moisture now: {pct}%",
        "sw": "Unyevu wa udongo sasa: {pct}%",
    },
    "hazard.why.drought_region": {
        "en": "This region is drought-prone",
        "sw": "Eneo hili lina hatari ya ukame",
    },
    "hazard.why.fire_weather": {
        "en": "Hottest, driest day {day}: {t}°C, humidity down to {rh}%, wind up to {wind} km/h",
        "sw": "Siku yenye joto na ukavu zaidi {day}: {t}°C, unyevu hewani hadi {rh}%, upepo hadi km/h {wind}",
    },
    "hazard.why.dry_days": {
        "en": "{n} of the next {total} days without rain",
        "sw": "Siku {n} kati ya {total} zijazo bila mvua",
    },
    "hazard.why.no_river": {
        "en": "No large river flows at this spot (river flow forecast)",
        "sw": "Hakuna mto mkubwa unaopita mahali hapa (utabiri wa mtiririko wa mito)",
    },
    "hazard.why.river": {
        "en": "River flow expected to reach {pct}% of this year's high-water level (peak {day})",
        "sw": "Mtiririko wa mto unatarajiwa kufikia {pct}% ya kiwango cha maji mengi cha mwaka huu (kilele {day})",
    },
    "hazard.why.heavy_rain": {
        "en": "Wettest 3 days in the forecast: {mm} mm (heaviest day {day_max} mm)",
        "sw": "Siku 3 zenye mvua nyingi zaidi katika utabiri: mm {mm} (siku yenye mvua nyingi mm {day_max})",
    },
    "hazard.rec.drought.low": {
        "en": "No drought expected. Keep following the irrigation advice on My farm.",
        "sw": "Hakuna ukame unaotarajiwa. Endelea kufuata ushauri wa umwagiliaji kwenye Shamba langu.",
    },
    "hazard.rec.drought.1": {
        "en": "Irrigate early in the morning or in the evening so less water evaporates.",
        "sw": "Mwagilia asubuhi mapema au jioni ili maji machache yapotee kwa mvuke.",
    },
    "hazard.rec.drought.2": {
        "en": "Mulch around your crops (dry grass or crop residue) to keep the soil moist.",
        "sw": "Weka matandazo kuzunguka mazao (majani makavu au mabaki ya mazao) ili udongo ubaki na unyevu.",
    },
    "hazard.rec.drought.3": {
        "en": "Give water first to crops that are flowering or filling grain; hold back on new planting.",
        "sw": "Toa maji kwanza kwa mazao yanayochanua au kujaza punje; subiri kupanda mapya.",
    },
    "hazard.rec.drought.4": {
        "en": "Consider weather-index (drought) insurance before the next planting season.",
        "sw": "Fikiria bima ya hali ya hewa (ukame) kabla ya msimu ujao wa kupanda.",
    },
    "hazard.rec.fire.low": {
        "en": "Fire danger is low. Keep grass short around your ghala and home.",
        "sw": "Hatari ya moto ni ndogo. Weka majani mafupi kuzunguka ghala na nyumbani.",
    },
    "hazard.rec.fire.1": {
        "en": "Do not burn crop residue or clear land with fire this week.",
        "sw": "Usichome mabaki ya mazao wala kusafisha shamba kwa moto wiki hii.",
    },
    "hazard.rec.fire.2": {
        "en": "Clear a firebreak: remove dry grass for about 3 m around fields, the ghala and stored harvest.",
        "sw": "Tengeneza njia ya kuzuia moto: ondoa majani makavu takriban mita 3 kuzunguka shamba, ghala na mavuno yaliyohifadhiwa.",
    },
    "hazard.rec.fire.3": {
        "en": "Keep water, sand and a beater ready near the ghala; agree with neighbours who to call.",
        "sw": "Weka maji, mchanga na kipigo tayari karibu na ghala; kubaliana na majirani nani wa kupigiwa simu.",
    },
    "hazard.rec.fire.4": {
        "en": "Move harvest stored in the open into the ghala, away from dry vegetation.",
        "sw": "Hamisha mavuno yaliyohifadhiwa nje ndani ya ghala, mbali na majani makavu.",
    },
    "hazard.rec.flood.low": {
        "en": "Flood risk is low. Keep drainage channels around fields clear.",
        "sw": "Hatari ya mafuriko ni ndogo. Weka mifereji ya maji kuzunguka shamba ikiwa safi.",
    },
    "hazard.rec.flood.1": {
        "en": "Clear drainage channels and ditches around fields and the ghala.",
        "sw": "Safisha mifereji na mitaro kuzunguka shamba na ghala.",
    },
    "hazard.rec.flood.2": {
        "en": "Raise stored harvest onto pallets and check the ghala roof for leaks.",
        "sw": "Inua mavuno yaliyohifadhiwa juu ya chaga na kagua paa la ghala kama linavuja.",
    },
    "hazard.rec.flood.3": {
        "en": "Harvest mature crops early and avoid planting in low-lying fields for now.",
        "sw": "Vuna mazao yaliyokomaa mapema na epuka kupanda katika mashamba ya bondeni kwa sasa.",
    },
    "hazard.rec.flood.4": {
        "en": "Move seed, fertiliser and equipment to higher ground; follow local authority warnings.",
        "sw": "Hamisha mbegu, mbolea na vifaa mahali pa juu; fuata tahadhari za mamlaka za eneo.",
    },
    "alert.hazard": {
        "en": "{hazard} risk is {level} for {farm} ({start} to {end}). See Finance → Insurance for what to do.",
        "sw": "Hatari ya {hazard} ni {level} kwa {farm} ({start} hadi {end}). Angalia Fedha → Bima kwa hatua za kuchukua.",
    },
    "hazard.name.drought": {
        "en": "Drought",
        "sw": "Ukame",
    },
    "hazard.name.fire": {
        "en": "Fire",
        "sw": "Moto",
    },
    "hazard.name.flood": {
        "en": "Flood",
        "sw": "Mafuriko",
    },
    "hazard.level.high": {
        "en": "high",
        "sw": "kubwa",
    },
    "hazard.level.severe": {
        "en": "very high",
        "sw": "kubwa sana",
    },
    "credit.src.sensor": {
        "en": "sensor",
        "sw": "kihisi",
    },
    "credit.src.estimate": {
        "en": "AI estimate",
        "sw": "makadirio ya AI",
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
