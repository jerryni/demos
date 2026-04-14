#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from lark_notifier import LarkNotifierError, send_text_from_config

BASE_URL = "https://ana-blue-hangar-tour.resv.jp/reserve/get_timetable_pc.php"

DEFAULT_PARAMS = {
    "view_mode": "month",
    "view_list": "1",
    "relation_mp": "1",
    "cur_year": "2026",
    "cur_month": "5",
    "cur_day": "15",
    "cur_mp_id": "0",
    "reserve_mode": "",
    "reserve_mode_user": "",
    "cancel_guest_hash": "",
    "pager_current": "1",
}

DEFAULT_HEADERS = {
    "accept": "text/html, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://ana-blue-hangar-tour.resv.jp/reserve/calendar.php?x=1776128229",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"iOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
    "x-requested-with": "XMLHttpRequest",
}

DEFAULT_COOKIE = "cookie_enable=1; TMPID_USR=6hm7ccadnasf3b2g28delvb4fkhmv6jd; cookie_enable=1"
DEFAULT_LARK_CONFIG = Path(__file__).with_name("lark_config.json")
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def parse_input_date(value: str) -> dt.date:
    candidates = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m-%d", "%m/%d")
    for fmt in candidates:
        try:
            parsed = dt.datetime.strptime(value, fmt)
            if "%Y" not in fmt:
                parsed = parsed.replace(year=int(DEFAULT_PARAMS["cur_year"]))
            return parsed.date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"无法识别日期格式: {value}，请使用 2026-05-15 / 2026/05/15 / 20260515。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="查询 ANA 页面中的 受付中 状态，并支持按日期汇总周六状态。"
    )
    parser.add_argument(
        "date",
        nargs="?",
        type=parse_input_date,
        default=dt.date(
            int(DEFAULT_PARAMS["cur_year"]),
            int(DEFAULT_PARAMS["cur_month"]),
            int(DEFAULT_PARAMS["cur_day"]),
        ),
        help="目标日期，例如 2026-05-15。",
    )
    parser.add_argument(
        "--report",
        choices=("open-dates", "saturdays"),
        default="saturdays",
        help="open-dates 查询当前页所有受付中日期；saturdays 汇总目标月份内周六状态。",
    )
    parser.add_argument("--view-mode", default=DEFAULT_PARAMS["view_mode"])
    parser.add_argument("--view-list", default=DEFAULT_PARAMS["view_list"])
    parser.add_argument("--relation-mp", default=DEFAULT_PARAMS["relation_mp"])
    parser.add_argument("--cur-mp-id", default=DEFAULT_PARAMS["cur_mp_id"])
    parser.add_argument("--reserve-mode", default=DEFAULT_PARAMS["reserve_mode"])
    parser.add_argument(
        "--reserve-mode-user", default=DEFAULT_PARAMS["reserve_mode_user"]
    )
    parser.add_argument(
        "--cancel-guest-hash", default=DEFAULT_PARAMS["cancel_guest_hash"]
    )
    parser.add_argument("--pager-current", default=DEFAULT_PARAMS["pager_current"])
    parser.add_argument(
        "--few-threshold",
        type=int,
        default=3,
        help="残りわずか 视为有效时要求的最小余量，默认 3。",
    )
    parser.add_argument("--request-ms", type=int, default=None)
    parser.add_argument(
        "--request-time",
        type=int,
        default=None,
        help="可选。接口不要求必须带 x-time；只有显式传入时才会拼上。",
    )
    parser.add_argument("--cookie", default=DEFAULT_COOKIE)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--strict-icon-circle-o",
        action="store_true",
        help="只把 icon-circle-o / 受付中 文本视为开放状态。",
    )
    parser.add_argument(
        "--include-adjacent-months",
        action="store_true",
        help="周六汇总时包含月历里前后相邻月份的日期。",
    )
    parser.add_argument(
        "--save-html",
        default=None,
        help="把返回的 HTML 保存到指定文件，便于排查。",
    )
    parser.add_argument(
        "--notify-lark-email",
        default=None,
        help="如果有命中结果，发送 Lark 私聊到该邮箱。",
    )
    parser.add_argument(
        "--lark-config",
        default=str(DEFAULT_LARK_CONFIG),
        help="Lark 配置文件路径，默认使用 ANA/lark_config.json。",
    )
    return parser.parse_args()


def build_query_params(args: argparse.Namespace, view_list: str | None = None) -> dict[str, str]:
    params = {
        "view_mode": args.view_mode,
        "view_list": view_list or args.view_list,
        "relation_mp": args.relation_mp,
        "cur_year": str(args.date.year),
        "cur_month": str(args.date.month),
        "cur_day": str(args.date.day),
        "cur_mp_id": args.cur_mp_id,
        "pager_current": args.pager_current,
        "reserve_mode": args.reserve_mode,
        "reserve_mode_user": args.reserve_mode_user,
        "cancel_guest_hash": args.cancel_guest_hash,
        "_": str(args.request_ms or int(time.time() * 1000)),
    }
    if args.request_time is not None:
        params["x-time"] = str(args.request_time)
    return params


def build_url(params: dict[str, str]) -> str:
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch_html(url: str, cookie: str, timeout: int) -> str:
    headers = DEFAULT_HEADERS.copy()
    headers["cookie"] = cookie
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def block_is_open(fragment: str, strict: bool) -> bool:
    normalized = fragment.replace('"', "'")
    if "受付中" in normalized or "icon-circle-o" in normalized:
        return True
    if strict:
        return False
    compatible_markers = (
        "icon-check-mark",
        "icon-open",
        "icon-available",
    )
    return any(marker in normalized for marker in compatible_markers)


def get_slot_status(fragment: str, strict: bool) -> str:
    normalized = fragment.replace('"', "'")
    if "icon-circle-o" in normalized or "受付中" in normalized:
        return "open"
    if "icon-history" in normalized:
        return "few"
    if "icon-cross-out-mark icon-full" in normalized:
        return "full"
    if "icon-cross-out-mark icon-outside" in normalized:
        return "outside"
    if not strict and any(
        marker in normalized for marker in ("icon-check-mark", "icon-open", "icon-available")
    ):
        return "open"
    return "unknown"


def extract_day_records_from_month_view(html_text: str, strict: bool) -> dict[str, list[dict[str, str]]]:
    records: dict[str, list[dict[str, str]]] = {}
    for match in re.finditer(r"<td\b.*?>.*?</td>", html_text, flags=re.S | re.I):
        fragment = match.group(0)
        date_match = re.search(
            r"changeViewModeDay\((\d{4}),(\d{1,2}),(\d{1,2})\)", fragment
        )
        if not date_match:
            continue

        year, month, day = map(int, date_match.groups())
        date_key = f"{year:04d}-{month:02d}-{day:02d}"
        slots: list[dict[str, str]] = []

        for slot_match in re.finditer(r"<ul\b.*?</ul>", fragment, flags=re.S | re.I):
            slot_html = slot_match.group(0)
            status = get_slot_status(slot_html, strict)
            if status == "unknown":
                continue

            time_match = re.search(r"<br[^>]*>\s*([^<\n]+)", slot_html, flags=re.I)
            remain_match = re.search(r'<span class="zannsu">(\d+)</span>', slot_html)

            slots.append(
                {
                    "status": status,
                    "time": time_match.group(1).strip() if time_match else "",
                    "remain": remain_match.group(1) if remain_match else "",
                }
            )

        records[date_key] = slots
    return records


def extract_open_dates_from_list_view(html_text: str, strict: bool) -> list[str]:
    dates: list[str] = []
    for match in re.finditer(r"<a\b.*?</a>", html_text, flags=re.S | re.I):
        fragment = match.group(0)
        if "touch-devi-list" not in fragment:
            continue
        if not block_is_open(fragment, strict):
            continue
        date_match = re.search(r"(\d{4})/(\d{2})/(\d{2})\s*\(", fragment)
        if not date_match:
            continue
        year, month, day = map(int, date_match.groups())
        dates.append(f"{year:04d}-{month:02d}-{day:02d}")
    return dates


def unique_keep_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def format_weekday(date_value: dt.date) -> str:
    return WEEKDAY_JA[date_value.weekday()]


def format_date_range(date_keys: list[str]) -> str:
    if not date_keys:
        return "未知"
    dates = sorted(dt.date.fromisoformat(date_key) for date_key in set(date_keys))
    return f"{dates[0].isoformat()} ~ {dates[-1].isoformat()}"


def slot_remain(slot: dict[str, str]) -> int | None:
    remain = slot.get("remain", "")
    return int(remain) if remain.isdigit() else None


def slot_matches_watch_rule(slot: dict[str, str], few_threshold: int) -> bool:
    if slot["status"] == "open":
        return True
    if slot["status"] == "few":
        remain = slot_remain(slot)
        return remain is not None and remain >= few_threshold
    return False


def summarize_slots(slots: list[dict[str, str]]) -> str:
    counts = {"open": 0, "few": 0, "full": 0, "outside": 0}
    open_times: list[str] = []
    for slot in slots:
        status = slot["status"]
        if status in counts:
            counts[status] += 1
        if status == "open":
            remain = f" 残{slot['remain']}" if slot["remain"] else ""
            open_times.append(f"{slot['time']}{remain}".strip())

    parts: list[str] = []
    if counts["open"]:
        parts.append(f"受付中 {counts['open']}枠")
    if counts["few"]:
        parts.append(f"残りわずか {counts['few']}枠")
    if counts["full"]:
        parts.append(f"満席 {counts['full']}枠")
    if counts["outside"]:
        parts.append(f"受付外 {counts['outside']}枠")
    if open_times:
        parts.append("开放时段: " + ", ".join(open_times))
    return "；".join(parts) if parts else "无班次"


def summarize_matched_slots(slots: list[dict[str, str]], few_threshold: int) -> str:
    matched_times = []
    for slot in slots:
        if not slot_matches_watch_rule(slot, few_threshold):
            continue
        remain = slot_remain(slot)
        remain_text = f" 残{remain}" if remain is not None else ""
        label = "受付中" if slot["status"] == "open" else "残りわずか"
        matched_times.append(f"{label} {slot['time']}{remain_text}".strip())
    return ", ".join(matched_times)


def print_report(lines: list[str]) -> None:
    for line in lines:
        print(line)


def maybe_send_lark_notification(
    args: argparse.Namespace, has_match: bool, lines: list[str]
) -> None:
    if not args.notify_lark_email or not has_match:
        return
    try:
        send_text_from_config(
            args.lark_config,
            "\n".join(lines),
            receive_id=args.notify_lark_email,
            receive_id_type="email",
        )
        print(f"Lark 通知已发送到: {args.notify_lark_email}")
    except LarkNotifierError as exc:
        print(f"Lark 通知发送失败: {exc}", file=sys.stderr)


def print_open_dates_report(args: argparse.Namespace) -> int:
    params = build_query_params(args)
    url = build_url(params)

    try:
        html_text = fetch_html(url, args.cookie, args.timeout)
    except Exception as exc:  # pragma: no cover
        print(f"请求失败: {exc}", file=sys.stderr)
        return 1

    if args.save_html:
        Path(args.save_html).write_text(html_text, encoding="utf-8")

    list_view_dates = extract_open_dates_from_list_view(html_text, args.strict_icon_circle_o)
    month_view_params = build_query_params(args, view_list="0")
    month_view_params["_"] = str(args.request_ms or int(time.time() * 1000))
    if args.request_time is not None:
        month_view_params["x-time"] = str(args.request_time)
    month_view_url = build_url(month_view_params)
    month_view_html = fetch_html(month_view_url, args.cookie, args.timeout)
    day_records = extract_day_records_from_month_view(
        month_view_html, args.strict_icon_circle_o
    )
    list_view_range = format_date_range(list_view_dates)
    month_view_range = format_date_range(list(day_records.keys()))
    qualifying_dates = [
        date_key
        for date_key, slots in day_records.items()
        if any(slot_matches_watch_rule(slot, args.few_threshold) for slot in slots)
    ]
    open_dates = unique_keep_order(list_view_dates + qualifying_dates)

    lines = [
        f"请求地址: {url}",
        f"匹配模式: {'严格 icon-circle-o' if args.strict_icon_circle_o else '兼容开放状态图标'}",
        f"附加规则: 残りわずか且余量>={args.few_threshold} 也计入命中",
        f"查询区间: 列表页 {list_view_range}；月历页 {month_view_range}",
    ]

    if open_dates:
        lines.append("当前页面存在符合条件的日期:")
        for date_key in open_dates:
            slots = day_records.get(date_key, [])
            summary = summarize_slots(slots)
            matched = summarize_matched_slots(slots, args.few_threshold)
            extra = f"；命中时段: {matched}" if matched else ""
            date_value = dt.date.fromisoformat(date_key)
            lines.append(f"{date_key} ({format_weekday(date_value)}): {summary}{extra}")
        has_match = True
    else:
        lines.append("当前页面没有找到符合条件的日期。")
        has_match = False
    print_report(lines)
    maybe_send_lark_notification(args, has_match, lines)
    return 0


def print_saturday_report(args: argparse.Namespace) -> int:
    params = build_query_params(args, view_list="0")
    url = build_url(params)

    try:
        html_text = fetch_html(url, args.cookie, args.timeout)
    except Exception as exc:  # pragma: no cover
        print(f"请求失败: {exc}", file=sys.stderr)
        return 1

    if args.save_html:
        Path(args.save_html).write_text(html_text, encoding="utf-8")

    day_records = extract_day_records_from_month_view(html_text, args.strict_icon_circle_o)
    saturday_items: list[tuple[dt.date, list[dict[str, str]]]] = []
    month_view_range = format_date_range(list(day_records.keys()))

    for date_key, slots in day_records.items():
        date_value = dt.date.fromisoformat(date_key)
        if date_value.weekday() != 5:
            continue
        if not args.include_adjacent_months and date_value.month != args.date.month:
            continue
        saturday_items.append((date_value, slots))

    saturday_items.sort(key=lambda item: item[0])

    lines = [
        f"请求地址: {url}",
        f"目标月份: {args.date.year:04d}-{args.date.month:02d}；筛选: 周六（土）",
        f"命中规则: 受付中，或 残りわずか且余量>={args.few_threshold}",
        f"查询区间: {month_view_range}",
    ]

    if not saturday_items:
        lines.append("当前区间内没有找到周六数据。")
        print_report(lines)
        return 0

    has_any_match = False
    for date_value, slots in saturday_items:
        has_match = any(
            slot_matches_watch_rule(slot, args.few_threshold) for slot in slots
        )
        has_any_match = has_any_match or has_match
        summary = summarize_slots(slots)
        matched_times = []
        for slot in slots:
            if not slot_matches_watch_rule(slot, args.few_threshold):
                continue
            remain = slot_remain(slot)
            remain_text = f" 残{remain}" if remain is not None else ""
            label = "受付中" if slot["status"] == "open" else "残りわずか"
            matched_times.append(f"{label} {slot['time']}{remain_text}".strip())
        matched_text = (
            "；命中时段: " + ", ".join(matched_times) if matched_times else ""
        )
        lines.append(
            f"{date_value.isoformat()} ({format_weekday(date_value)}): "
            f"{'有符合条件时段' if has_match else '无符合条件时段'}；{summary}{matched_text}"
        )
    print_report(lines)
    maybe_send_lark_notification(args, has_any_match, lines)
    return 0


def main() -> int:
    args = parse_args()
    if args.report == "open-dates":
        return print_open_dates_report(args)
    return print_saturday_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
