"""USSD conversation engine — menus call shared application services.

Menu tree (mirrors the web farmer app):
  Registration → name, region (location), farm size, crop + acres → AI soil/weather summary
  1 Farm    → crops on the page; info, AI conditions, crop advice, add crop (+acres), irrigation
  2 Ghala   → AI room forecast + quick actions, stored stock, ghala alerts
  3 Market  → listed stock, sales history, buyer requests, prices
  4 Finance → loans (apply / status), savings (goals / deposit / new goal),
              insurance (report disaster / my cover / request cover), financial status
"""

from __future__ import annotations

import logging
import re

from sqlmodel import Session

from ..ai.soil_map import REGIONS
from ..communication.exceptions import InvalidPhoneError
from ..communication.phone import mask_phone, normalize_phone
from ..communication.providers.base import USSDRequest, USSDResponse
from ..i18n import bi, crop_name, t
from ..models import SavingsGoal
from . import services, states
from .sessions import get_or_create_session, set_state

log = logging.getLogger(__name__)

MAX_INPUT_LEN = 160
REGION_PAGE_SIZE = 8
REGION_MORE = "9"
MAX_AMOUNT_TZS = 100_000_000


def _last_input(text: str) -> str:
    """Africa's Talking sends the full path as '1*2*3'; Beem may send only the latest digit."""
    if not text:
        return ""
    parts = [p for p in str(text).split("*") if p != ""]
    return parts[-1].strip() if parts else ""


def _options(lang: str, title: str, options: list[tuple[str, str]], header: str = "") -> str:
    lines = [title] + ([header] if header else []) + [""]
    lines += [f"{key}. {t(label_key, lang)}" for key, label_key in options]
    return "\n".join(lines).strip()


def _menu(lang: str, title_key: str, options: list[tuple[str, str]], header: str = "") -> str:
    return _options(lang, t(title_key, lang), options, header)


def _end(message: str) -> USSDResponse:
    return USSDResponse(message=message, continue_session=False)


def _con(message: str) -> USSDResponse:
    return USSDResponse(message=message, continue_session=True)


def _invalid(lang: str) -> str:
    return t("ussd.error.invalid", lang)


def _retry(screen: str, lang: str) -> USSDResponse:
    return _con(screen + "\n" + _invalid(lang))


def _amount(choice: str) -> float | None:
    try:
        value = float(choice.replace(",", ""))
    except ValueError:
        return None
    return value if 0 < value <= MAX_AMOUNT_TZS else None


def _acres(choice: str) -> float | None:
    try:
        value = float(choice.replace(",", "."))
    except ValueError:
        return None
    return value if 0 < value <= 10_000 else None


def _payload(ussd) -> dict:
    return dict(ussd.payload or {})


def handle_ussd(session: Session, request: USSDRequest, *, provider_name: str) -> USSDResponse:
    try:
        phone = normalize_phone(request.phone_number)
    except InvalidPhoneError:
        return _end(t("ussd.error.phone", "sw"))

    user, farmer = services.find_farmer_user(session, phone)
    ussd = get_or_create_session(
        session,
        session_id=request.session_id or f"{phone}-{request.service_code}",
        phone_number=phone,
        provider=provider_name,
        user_id=user.id if user else None,
    )

    raw_text = (request.text or "")[:MAX_INPUT_LEN]
    choice = _last_input(raw_text)
    lang = services.lang_of(user)

    # Brand-new session (empty text): registration first, otherwise the main menu.
    if raw_text == "" and ussd.state in (states.MAIN_MENU, states.UNREGISTERED):
        if farmer and user and user.status == "ACTIVE":
            set_state(ussd, states.MAIN_MENU)
            resp = _con(_main_menu(lang))
        else:
            set_state(ussd, states.UNREGISTERED)
            resp = _con(_unregistered_menu(lang))
        _log(ussd, "OK")
        return resp

    session_id = ussd.session_id
    try:
        resp = _dispatch(session, ussd, user, farmer, choice, lang)
    except Exception:
        log.exception("USSD handler error session=%s phone=%s", session_id, mask_phone(phone))
        session.rollback()  # never keep half-done writes (e.g. a consent without its loan)
        return _end(t("ussd.error.unavailable", lang))
    _log(ussd, "END" if not resp.continue_session else "OK")
    return resp


def _log(ussd, status: str) -> None:
    log.info("USSD session=%s phone=%s state=%s status=%s", ussd.session_id, mask_phone(ussd.phone_number), ussd.state, status)


# ---------------------------------------------------------------- screens


def _main_menu(lang: str) -> str:
    return _menu(
        lang,
        "ussd.main.title",
        [("1", "ussd.main.farm"), ("2", "ussd.main.ghala"), ("3", "ussd.main.market"), ("4", "ussd.main.finance"), ("0", "ussd.main.exit")],
    )


def _unregistered_menu(lang: str) -> str:
    return _menu(lang, "ussd.unregistered.title", [("1", "ussd.unregistered.register"), ("0", "ussd.main.exit")])


def _region_menu(lang: str, page: int) -> str:
    start = page * REGION_PAGE_SIZE
    lines = [t("ussd.reg.region", lang)]
    lines += [f"{i}. {r.name}" for i, r in enumerate(REGIONS[start : start + REGION_PAGE_SIZE], start=1)]
    if start + REGION_PAGE_SIZE < len(REGIONS):
        lines.append(f"{REGION_MORE}. {t('ussd.nav.more', lang)}")
    if page > 0:
        lines.append(f"0. {t('ussd.nav.back', lang)}")
    return "\n".join(lines)


def _crop_menu(lang: str, *, include_none: bool = False, include_back: bool = False) -> str:
    options = [(k, f"ussd.reg.crop.{v}") for k, v in services.CROP_CHOICES.items()]
    if include_none:
        options.append((services.NO_CROP_CHOICE, "ussd.reg.crop.none"))
    if include_back:
        options.append(("0", "ussd.nav.back"))
    return _menu(lang, "ussd.reg.crop_title", options)


def _crop_acres_prompt(lang: str, crop_type: str, farm_acres: float) -> str:
    return t("ussd.crop.acres", lang, crop=crop_name(crop_type)[lang].capitalize(), max=farm_acres)


def _farm_menu(session, farmer, lang: str) -> str:
    return _menu(
        lang,
        "ussd.farm.title",
        [
            ("1", "ussd.farm.info_opt"),
            ("2", "ussd.farm.conditions_opt"),
            ("3", "ussd.farm.planting_opt"),
            ("4", "ussd.farm.add_crop_opt"),
            ("5", "ussd.farm.irrigation_opt"),
            ("0", "ussd.nav.back"),
        ],
        header=t("ussd.farm.crops_line", lang, crops=services.crops_summary(session, farmer, lang, with_stage=False)),
    )


def _ghala_menu(session, farmer, lang: str) -> str:
    return _menu(
        lang,
        "ussd.ghala.title",
        [("1", "ussd.ghala.outlook_opt"), ("2", "ussd.ghala.stock_opt"), ("3", "ussd.ghala.alerts_opt"), ("0", "ussd.nav.back")],
        header=services.ghala_summary(session, farmer, lang),
    )


def _market_menu(lang: str) -> str:
    return _menu(
        lang,
        "ussd.market.title",
        [
            ("1", "ussd.market.stock_opt"),
            ("2", "ussd.market.sales_opt"),
            ("3", "ussd.market.requests_opt"),
            ("4", "ussd.market.prices_opt"),
            ("0", "ussd.nav.back"),
        ],
    )


def _finance_menu(lang: str) -> str:
    return _menu(
        lang,
        "ussd.finance.title",
        [
            ("1", "ussd.finance.loans_opt"),
            ("2", "ussd.finance.savings_opt"),
            ("3", "ussd.finance.insurance_opt"),
            ("4", "ussd.finance.profile_opt"),
            ("0", "ussd.nav.back"),
        ],
    )


def _loans_menu(lang: str) -> str:
    return _menu(lang, "ussd.loan.title", [("1", "ussd.loan.apply_opt"), ("2", "ussd.loan.status_opt"), ("0", "ussd.nav.back")])


def _savings_menu(lang: str) -> str:
    return _menu(
        lang,
        "ussd.savings.menu_title",
        [("1", "ussd.savings.view_opt"), ("2", "ussd.savings.deposit_opt"), ("3", "ussd.savings.new_opt"), ("0", "ussd.nav.back")],
    )


def _insurance_menu(lang: str) -> str:
    return _menu(
        lang,
        "ussd.ins.title",
        [("1", "ussd.ins.report_opt"), ("2", "ussd.ins.mine_opt"), ("3", "ussd.ins.request_opt"), ("0", "ussd.nav.back")],
    )


def _loan_purpose_menu(lang: str) -> str:
    return _menu(lang, "ussd.loan.purpose_title", [(k, f"ussd.loan.purpose.{v}") for k, v in services.LOAN_PURPOSES.items()])


def _disaster_menu(lang: str) -> str:
    options = [(k, f"ussd.disaster.{v}") for k, v in services.DISASTERS.items()] + [("0", "ussd.nav.back")]
    return _menu(lang, "ussd.disaster.title", options)


def _bucket_menu(lang: str) -> str:
    return _menu(lang, "ussd.savings.bucket_title", [(k, f"savings.{v}") for k, v in services.SAVINGS_BUCKETS.items()])


def _goal_menu(goals: list[SavingsGoal], lang: str) -> str:
    lines = [t("ussd.savings.pick_goal", lang)]
    lines += [f"{i}. {g.name}" for i, g in enumerate(goals[: services.MAX_LIST], start=1)]
    return "\n".join(lines)


# ---------------------------------------------------------------- dispatch


def _dispatch(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    state = ussd.state

    if state == states.UNREGISTERED:
        return _handle_unregistered(ussd, choice, lang)
    if state.startswith("REGISTRATION_"):
        return _handle_registration(session, ussd, choice, lang)

    if not farmer or not user:
        set_state(ussd, states.UNREGISTERED)
        return _con(_unregistered_menu(lang))

    ctx = (session, ussd, user, farmer, choice, lang)
    handlers = {
        states.MAIN_MENU: _handle_main,
        states.FARM_MENU: _handle_farm_menu,
        states.FARM_ADD_CROP: _handle_add_crop,
        states.FARM_ADD_CROP_ACRES: _handle_add_crop_acres,
        states.GHALA_MENU: _handle_ghala_menu,
        states.MARKET_MENU: _handle_market_menu,
        states.FINANCE_MENU: _handle_finance_menu,
        states.FINANCE_PROFILE: _handle_finance_profile,
        states.LOANS_MENU: _handle_loans_menu,
        states.LOAN_AMOUNT: _handle_loan_amount,
        states.LOAN_PURPOSE: _handle_loan_purpose,
        states.LOAN_PIN: _handle_loan_pin,
        states.SAVINGS_MENU: _handle_savings_menu,
        states.SAVINGS_DEPOSIT_GOAL: _handle_deposit_goal,
        states.SAVINGS_DEPOSIT_AMOUNT: _handle_deposit_amount,
        states.SAVINGS_NEW_BUCKET: _handle_new_bucket,
        states.SAVINGS_NEW_TARGET: _handle_new_target,
        states.INSURANCE_MENU: _handle_insurance_menu,
        states.DISASTER_TYPE: _handle_disaster_type,
        states.DISASTER_CONFIRM: _handle_disaster_confirm,
        states.INSURANCE_REQUEST: _handle_insurance_request,
        states.INSURANCE_PIN: _handle_insurance_pin,
    }
    handler = handlers.get(state)
    if not handler:
        set_state(ussd, states.MAIN_MENU)
        return _con(_main_menu(lang))
    return handler(*ctx)


# ---------------------------------------------------------------- registration


def _handle_unregistered(ussd, choice, lang) -> USSDResponse:
    if choice == "1":
        set_state(ussd, states.REGISTRATION_NAME, draft={})
        return _con(t("ussd.reg.name", lang))
    if choice == "0":
        return _end(t("ussd.main.goodbye", lang))
    return _con(_unregistered_menu(lang) + "\n\n" + _invalid(lang))


def _handle_registration(session, ussd, choice, lang) -> USSDResponse:
    payload = _payload(ussd)
    draft = dict(payload.get("draft") or {})
    state = ussd.state

    if state == states.REGISTRATION_NAME:
        name = choice.strip()
        if len(name) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", name):
            return _retry(t("ussd.reg.name", lang), lang)
        draft["full_name"] = name[:80]
        set_state(ussd, states.REGISTRATION_LOCATION, draft=draft, region_page=0)
        return _con(_region_menu(lang, 0))

    if state == states.REGISTRATION_LOCATION:
        page = int(payload.get("region_page") or 0)
        page_regions = REGIONS[page * REGION_PAGE_SIZE : (page + 1) * REGION_PAGE_SIZE]
        has_more = (page + 1) * REGION_PAGE_SIZE < len(REGIONS)
        if choice == REGION_MORE and has_more:
            set_state(ussd, states.REGISTRATION_LOCATION, region_page=page + 1)
            return _con(_region_menu(lang, page + 1))
        if choice == "0" and page > 0:
            set_state(ussd, states.REGISTRATION_LOCATION, region_page=page - 1)
            return _con(_region_menu(lang, page - 1))
        if not choice.isdigit() or not 1 <= int(choice) <= len(page_regions):
            return _retry(_region_menu(lang, page), lang)
        draft["region"] = page_regions[int(choice) - 1].name
        set_state(ussd, states.REGISTRATION_SIZE, draft=draft)
        return _con(t("ussd.reg.size", lang))

    if state == states.REGISTRATION_SIZE:
        acres = _acres(choice)
        if acres is None:
            return _retry(t("ussd.reg.size", lang), lang)
        draft["acreage"] = acres
        set_state(ussd, states.REGISTRATION_CROP, draft=draft)
        return _con(_crop_menu(lang, include_none=True))

    if state == states.REGISTRATION_CROP:
        if choice == services.NO_CROP_CHOICE:
            return _complete_registration(session, ussd, draft, lang)
        crop = services.CROP_CHOICES.get(choice)
        if not crop:
            return _retry(_crop_menu(lang, include_none=True), lang)
        draft["crop_type"] = crop
        set_state(ussd, states.REGISTRATION_CROP_ACRES, draft=draft)
        return _con(_crop_acres_prompt(lang, crop, draft["acreage"]))

    if state == states.REGISTRATION_CROP_ACRES:
        acres = _acres(choice)
        if acres is None or acres > draft["acreage"]:
            return _retry(_crop_acres_prompt(lang, draft["crop_type"], draft["acreage"]), lang)
        draft["crop_acreage"] = acres
        return _complete_registration(session, ussd, draft, lang)

    set_state(ussd, states.UNREGISTERED)
    return _con(_unregistered_menu(lang))


def _complete_registration(session, ussd, draft: dict, lang: str) -> USSDResponse:
    user, _farmer, farm, pin = services.register_farmer(
        session,
        ussd.phone_number,
        full_name=draft.get("full_name", "Mkulima"),
        region=draft.get("region", "Dodoma"),
        acreage=float(draft.get("acreage") or 1),
        crop_type=draft.get("crop_type"),
        crop_acreage=draft.get("crop_acreage"),
    )
    ussd.user_id = user.id
    set_state(ussd, states.MAIN_MENU, draft={})
    try:
        from ..communication.sms import send_sms

        send_sms(session, user, bi("ussd.reg.pin_sms", pin=pin), event_type="SYSTEM_NOTIFICATION")
    except Exception:
        log.warning("Could not SMS USSD registration PIN")
    return _end(services.registration_summary(session, farm, lang))


# ---------------------------------------------------------------- main


def _handle_main(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        set_state(ussd, states.FARM_MENU)
        return _con(_farm_menu(session, farmer, lang))
    if choice == "2":
        set_state(ussd, states.GHALA_MENU)
        return _con(_ghala_menu(session, farmer, lang))
    if choice == "3":
        set_state(ussd, states.MARKET_MENU)
        return _con(_market_menu(lang))
    if choice == "4":
        set_state(ussd, states.FINANCE_MENU)
        return _con(_finance_menu(lang))
    if choice == "0":
        return _end(t("ussd.main.goodbye", lang))
    return _con(_main_menu(lang) + "\n\n" + _invalid(lang))


def _back_to_main(ussd, lang) -> USSDResponse:
    set_state(ussd, states.MAIN_MENU)
    return _con(_main_menu(lang))


# ---------------------------------------------------------------- farm


def _handle_farm_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        return _end(services.farm_info_text(session, farmer, lang))
    if choice == "2":
        return _end(services.farm_conditions_text(session, farmer, lang))
    if choice == "3":
        return _end(services.planting_text(session, farmer, lang))
    if choice == "4":
        set_state(ussd, states.FARM_ADD_CROP)
        return _con(_crop_menu(lang, include_back=True))
    if choice == "5":
        return _end(services.irrigation_text(session, farmer, lang))
    if choice == "0":
        return _back_to_main(ussd, lang)
    return _retry(_farm_menu(session, farmer, lang), lang)


def _handle_add_crop(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "0":
        set_state(ussd, states.FARM_MENU)
        return _con(_farm_menu(session, farmer, lang))
    crop_type = services.CROP_CHOICES.get(choice)
    if not crop_type:
        return _retry(_crop_menu(lang, include_back=True), lang)
    farm = services.primary_farm(session, farmer)
    if not farm:
        return _end(t("ussd.farm.none", lang))
    set_state(ussd, states.FARM_ADD_CROP_ACRES, crop_type=crop_type)
    return _con(_crop_acres_prompt(lang, crop_type, farm.acreage))


def _handle_add_crop_acres(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    crop_type = _payload(ussd).get("crop_type") or "maize"
    farm = services.primary_farm(session, farmer)
    if not farm:
        return _end(t("ussd.farm.none", lang))
    acres = _acres(choice)
    if acres is None or acres > farm.acreage:
        return _retry(_crop_acres_prompt(lang, crop_type, farm.acreage), lang)
    services.add_crop(session, farmer, crop_type, acres)
    return _end(t("ussd.farm.crop_added", lang, crop=crop_name(crop_type)[lang].capitalize(), acres=acres))


# ---------------------------------------------------------------- ghala


def _handle_ghala_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        return _end(services.ghala_outlook_text(session, farmer, lang))
    if choice == "2":
        return _end(services.ghala_stock_text(session, farmer, lang))
    if choice == "3":
        return _end(services.alerts_text(session, user, lang, kinds={"SPOILAGE_RISK"}))
    if choice == "0":
        return _back_to_main(ussd, lang)
    return _retry(_ghala_menu(session, farmer, lang), lang)


# ---------------------------------------------------------------- market


def _handle_market_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        return _end(services.market_listed_text(session, farmer, lang))
    if choice == "2":
        return _end(services.sales_history_text(session, farmer, lang))
    if choice == "3":
        return _end(services.market_requests_text(session, farmer, lang))
    if choice == "4":
        return _end(services.market_prices_text(session, farmer, lang))
    if choice == "0":
        return _back_to_main(ussd, lang)
    return _retry(_market_menu(lang), lang)


# ---------------------------------------------------------------- finance


def _handle_finance_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        set_state(ussd, states.LOANS_MENU)
        return _con(_loans_menu(lang))
    if choice == "2":
        set_state(ussd, states.SAVINGS_MENU)
        return _con(_savings_menu(lang))
    if choice == "3":
        set_state(ussd, states.INSURANCE_MENU)
        return _con(_insurance_menu(lang))
    if choice == "4":
        set_state(ussd, states.FINANCE_PROFILE)
        text = services.finance_profile_text(session, farmer, lang)
        return _con(text + "\n\n1. " + t("ussd.finance.why_opt", lang) + "\n0. " + t("ussd.nav.back", lang))
    if choice == "0":
        return _back_to_main(ussd, lang)
    return _retry(_finance_menu(lang), lang)


def _back_to_finance(ussd, lang) -> USSDResponse:
    set_state(ussd, states.FINANCE_MENU)
    return _con(_finance_menu(lang))


def _handle_finance_profile(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        return _end(services.finance_why_text(session, farmer, lang))
    if choice == "0":
        return _back_to_finance(ussd, lang)
    return _con(_invalid(lang))


# loans


def _loan_amount_prompt(session, farmer, lang) -> str:
    suggestion = services.suggested_loan(session, farmer)
    if suggestion:
        return t("ussd.loan.amount_suggested", lang, amount=services.tzs(suggestion.get("max_amount_tzs", 0)))
    return t("ussd.loan.amount", lang)


def _handle_loans_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        set_state(ussd, states.LOAN_AMOUNT)
        return _con(_loan_amount_prompt(session, farmer, lang))
    if choice == "2":
        return _end(services.loans_text(session, farmer, lang))
    if choice == "0":
        return _back_to_finance(ussd, lang)
    return _retry(_loans_menu(lang), lang)


def _handle_loan_amount(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    amount = _amount(choice)
    if amount is None:
        return _retry(_loan_amount_prompt(session, farmer, lang), lang)
    set_state(ussd, states.LOAN_PURPOSE, loan_amount=amount)
    return _con(_loan_purpose_menu(lang))


def _handle_loan_purpose(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    purpose = services.LOAN_PURPOSES.get(choice)
    if not purpose:
        return _retry(_loan_purpose_menu(lang), lang)
    set_state(ussd, states.LOAN_PIN, loan_purpose=purpose)
    amount = _payload(ussd)["loan_amount"]
    return _con(t("ussd.loan.confirm_pin", lang, amount=services.tzs(amount), purpose=t(f"ussd.loan.purpose.{purpose}", lang)))


def _handle_loan_pin(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if not services.verify_pin(user, choice):
        return _end(t("ussd.pin.wrong", lang))
    payload = _payload(ussd)
    result = services.apply_loan(session, user, farmer, float(payload["loan_amount"]), payload["loan_purpose"])
    if not result:
        return _end(t("ussd.loan.no_lender", lang))
    loan, lender = result
    set_state(ussd, states.FINANCE_MENU)
    return _end(t("ussd.loan.sent", lang, id=loan.id, amount=services.tzs(loan.amount), lender=lender.full_name))


# savings


def _handle_savings_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        return _end(services.savings_text(session, farmer, lang))
    if choice == "2":
        goals = services.savings_goals(session, farmer)
        if not goals:
            set_state(ussd, states.SAVINGS_NEW_BUCKET)
            return _con(t("ussd.savings.none", lang) + "\n" + _bucket_menu(lang))
        set_state(ussd, states.SAVINGS_DEPOSIT_GOAL)
        return _con(_goal_menu(goals, lang))
    if choice == "3":
        set_state(ussd, states.SAVINGS_NEW_BUCKET)
        return _con(_bucket_menu(lang))
    if choice == "0":
        return _back_to_finance(ussd, lang)
    return _retry(_savings_menu(lang), lang)


def _handle_deposit_goal(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    goals = services.savings_goals(session, farmer)[: services.MAX_LIST]
    if not choice.isdigit() or not 1 <= int(choice) <= len(goals):
        return _retry(_goal_menu(goals, lang), lang)
    goal = goals[int(choice) - 1]
    set_state(ussd, states.SAVINGS_DEPOSIT_AMOUNT, goal_id=goal.id)
    return _con(t("ussd.savings.deposit_amount", lang, goal=goal.name))


def _handle_deposit_amount(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    goal = session.get(SavingsGoal, _payload(ussd).get("goal_id"))
    if not goal or goal.farmer_id != farmer.id:
        return _end(t("ussd.error.unavailable", lang))
    amount = _amount(choice)
    if amount is None:
        return _retry(t("ussd.savings.deposit_amount", lang, goal=goal.name), lang)
    services.deposit(session, goal, amount)
    return _end(
        t("ussd.savings.deposited", lang, amount=services.tzs(amount), goal=goal.name, saved=f"{goal.saved_amount:,.0f}", target=f"{goal.target_amount:,.0f}")
    )


def _handle_new_bucket(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    bucket = services.SAVINGS_BUCKETS.get(choice)
    if not bucket:
        return _retry(_bucket_menu(lang), lang)
    set_state(ussd, states.SAVINGS_NEW_TARGET, bucket=bucket)
    return _con(t("ussd.savings.target", lang, bucket=t(f"savings.{bucket}", lang)))


def _handle_new_target(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    bucket = _payload(ussd).get("bucket") or "goal"
    target = _amount(choice)
    if target is None:
        return _retry(t("ussd.savings.target", lang, bucket=t(f"savings.{bucket}", lang)), lang)
    goal = services.create_goal(session, farmer, bucket, target, lang)
    return _end(t("ussd.savings.created", lang, goal=goal.name, target=services.tzs(target)))


# insurance


def _handle_insurance_menu(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "1":
        set_state(ussd, states.DISASTER_TYPE)
        return _con(_disaster_menu(lang))
    if choice == "2":
        return _end(services.policies_text(session, farmer, lang))
    if choice == "3":
        options = services.insurance_options(session, farmer)
        if not options:
            return _end(t("ussd.ins.no_options", lang))
        set_state(ussd, states.INSURANCE_REQUEST)
        return _con(services.insurance_options_text(options, lang))
    if choice == "0":
        return _back_to_finance(ussd, lang)
    return _retry(_insurance_menu(lang), lang)


def _handle_disaster_type(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if choice == "0":
        set_state(ussd, states.INSURANCE_MENU)
        return _con(_insurance_menu(lang))
    disaster = services.DISASTERS.get(choice)
    if not disaster:
        return _retry(_disaster_menu(lang), lang)
    policy = services.policy_for_disaster(session, farmer, disaster)
    if not policy:
        return _end(t("ussd.disaster.no_policy", lang))
    set_state(ussd, states.DISASTER_CONFIRM, disaster=disaster, policy_id=policy.id)
    return _con(
        t("ussd.disaster.confirm", lang, disaster=t(f"ussd.disaster.{disaster}", lang), policy=policy.id, product=t(f"ussd.product.{policy.product}", lang))
    )


def _handle_disaster_confirm(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    payload = _payload(ussd)
    if choice == "0":
        set_state(ussd, states.INSURANCE_MENU)
        return _con(_insurance_menu(lang))
    if choice != "1":
        return _con(_invalid(lang))
    policy = next((p for p in services.active_policies(session, farmer) if p.id == payload.get("policy_id")), None)
    if not policy:
        return _end(t("ussd.disaster.no_policy", lang))
    claim = services.report_disaster(session, user, farmer, policy, payload.get("disaster") or "drought")
    return _end(t("ussd.disaster.sent", lang, id=claim.id))


def _handle_insurance_request(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    options = services.insurance_options(session, farmer)
    if choice == "0":
        set_state(ussd, states.INSURANCE_MENU)
        return _con(_insurance_menu(lang))
    if not choice.isdigit() or not 1 <= int(choice) <= len(options):
        return _retry(services.insurance_options_text(options, lang), lang)
    option = options[int(choice) - 1]
    set_state(ussd, states.INSURANCE_PIN, ins_option=int(choice) - 1)
    return _con(t("ussd.ins.confirm_pin", lang, product=t(f"ussd.product.{option['product']}", lang), premium=services.tzs(option["indicative_premium_tzs"])))


def _handle_insurance_pin(session, ussd, user, farmer, choice, lang) -> USSDResponse:
    if not services.verify_pin(user, choice):
        return _end(t("ussd.pin.wrong", lang))
    options = services.insurance_options(session, farmer)
    index = int(_payload(ussd).get("ins_option") or 0)
    if index >= len(options):
        return _end(t("ussd.ins.no_options", lang))
    result = services.request_policy(session, user, farmer, options[index])
    if not result:
        return _end(t("ussd.ins.no_insurer", lang))
    policy, insurer = result
    return _end(t("ussd.ins.sent", lang, id=policy.id, insurer=insurer.full_name))
