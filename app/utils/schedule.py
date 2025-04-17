import logging
from typing import Optional
from datetime import date, timedelta
from collections import defaultdict
import httpx
from app.config import TIMETABLE_HEADERS
from app.lexicon.lexicon import LEXICON_MSG
from app.utils.date_utils import get_day_name
from app.db.crud.user import get_attendance_data

logger = logging.getLogger(__name__)

async def get_token(login: str, password: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://inet.mdis.uz/oauth/tocken",
                headers=TIMETABLE_HEADERS,
                data={
                    "username": login,
                    "password": password,
                    "grant_type": "password"
                }
            )
            if response.status_code == 200:
                logger.info(f"Successfully obtained token for user {login}")
                return response.json().get("access_token")
            logger.warning(f"Failed to obtain token for user {login}, status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error obtaining token for user {login}: {str(e)}", exc_info=True)
        return None

async def fetch_user_data(token: str, inet_id: str) -> list:
    try:
        headers = TIMETABLE_HEADERS.copy()
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://inet.mdis.uz/api/v1/education/view/students?selfId={inet_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json().get("data", [])
                logger.info(f"Successfully fetched user data for inet_id {inet_id}")
                return data
            logger.warning(f"Failed to fetch user data for inet_id {inet_id}, status code: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching user data for inet_id {inet_id}: {str(e)}", exc_info=True)
        return []

async def fetch_schedule_data(token: str, start: date, end: date) -> list:
    try:
        headers = TIMETABLE_HEADERS.copy()
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://inet.mdis.uz/api/v1/education/student/view/schedules?from={start}&to={end}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json().get("data", [])
                logger.info(f"Successfully fetched schedule data from {start} to {end}")
                return data
            logger.warning(f"Failed to fetch schedule data from {start} to {end}, status code: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching schedule data from {start} to {end}: {str(e)}", exc_info=True)
        return []


async def format_schedule(data: list, lang: str = "en") -> str:
    if not data:
        return LEXICON_MSG['no_classes'][lang]

    data.sort(key=lambda x: (x["scheduleDate"], x["startTime"]))
    grouped = defaultdict(list)

    for lesson in data:
        day_name = get_day_name(lesson["scheduleDate"])
        time = f"{lesson['startTime'][:-3]}–{lesson['endTime'][:-3]}"
        subject = lesson["moduleName"]
        venue = lesson["venueName"]
        lecturer = lesson["lecturerName"]
        lesson_type = lesson["lessonTypeName"]
        schedule_status = lesson["scheduleStatus"]

        lesson_text = ()

        if schedule_status == "ACTIVE":
            lesson_text = (
                f"🕐 {time} — {subject} ({lesson_type})\n"
                f"🏫 {LEXICON_MSG['classroom'][lang]}: {venue}\n"
                f"👨‍🏫 {LEXICON_MSG['teacher'][lang]}: {lecturer}\n"
            )
        else:
            lesson_text = (
                f"🟥 CANCELED 🟥\n"
                f"<del>🕐 {time} — {subject} ({lesson_type})</del>\n"
                f"<del>🏫 {LEXICON_MSG['classroom'][lang]}: {venue}</del>\n"
                f"<del>👨‍🏫 {LEXICON_MSG['teacher'][lang]}: {lecturer}</del>\n"
            )
        grouped[day_name].append(lesson_text)

    final_lines = []
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
        if day in grouped:
            final_lines.append(f"📅 <b>{LEXICON_MSG['days'][lang][day]}</b>")
            final_lines.extend(grouped[day])
            final_lines.append("")

    return "\n".join(final_lines)

async def fetch_attendance_data(telegram_id: int, token: str) -> list:
    try:
        inet_id, semester_id = await get_attendance_data(telegram_id)
        headers = TIMETABLE_HEADERS.copy()
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://inet.mdis.uz/api/v1/education/students/attendances?page=0&perPage=10&direction=ASC&sortBy=id&semesterId={semester_id}&studentId={inet_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json().get("data", [])
                logger.info(f"Successfully fetched attendance data for user {telegram_id}")
                return data
            logger.warning(f"Failed to fetch attendance data for user {telegram_id}, status code: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching attendance data for user {telegram_id}: {str(e)}", exc_info=True)
        return []

def format_attendance(data: list, lang: str = "ru") -> str:
    if not data:
        return LEXICON_MSG['no_absences'][lang]

    final_lines = []
    data.sort(key=lambda x: x["name"])

    for lesson in data:
        subject = lesson["name"]
        code = lesson["code"]
        seminar_hours = lesson["seminarHours"]
        lecture_hours = lesson["lectureHours"]
        absent_count = lesson["absenseCount"]
        attendance_percent = lesson["attendancePercent"]

        if attendance_percent < 16:
            emoji = "🟩"
        elif 16 <= attendance_percent < 20:
            emoji = "🟨"
        else:
            emoji = "🟥"

        line = (
            f"{emoji} <b>{subject}</b> ({code})\n"
            f"🧑‍🏫 {LEXICON_MSG['seminar_hours'][lang]}: {seminar_hours} | {LEXICON_MSG['lecture_hours'][lang]}: {lecture_hours}\n"
            f"❌ {LEXICON_MSG['absences'][lang]}: {absent_count} ({attendance_percent}%)\n"
        )
        final_lines.append(line)

    return "\n".join(final_lines)

def sanitize_schedule_data(data: list[dict]) -> list[dict]:
    needed_fields = [
        "scheduleDate",
        "startTime",
        "endTime",
        "moduleName",
        "venueName",
        "lecturerName",
        "lessonTypeName",
        "scheduleStatus"
    ]
    return [
        {key: item[key] for key in needed_fields if key in item}
        for item in data
    ]

def get_week_start(date_: date) -> date:
    return date_ - timedelta(days=date_.weekday())