"""Email notification helpers.

Sends HTML emails via SMTP.  When SMTP_HOST is empty (default) the function
logs the message instead so the app starts cleanly without an SMTP server.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> None:
    if not settings.smtp_host or not settings.email_from:
        logger.info("[email-stub] to=%s | subject=%s", to, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as srv:
            srv.ehlo()
            if settings.smtp_use_tls:
                srv.starttls()
            if settings.smtp_user:
                srv.login(settings.smtp_user, settings.smtp_password)
            srv.sendmail(settings.email_from, to, msg.as_string())
        logger.info("[email] sent to=%s subject=%s", to, subject)
    except Exception as exc:
        logger.error("[email] failed to=%s error=%s", to, exc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


def send_booking_confirmation(
    user_email: str,
    user_name: str,
    table_number: str,
    start_time: datetime,
    end_time: datetime,
    party_size: int,
) -> None:
    html = f"""
    <h2>ยืนยันการจองโต๊ะ</h2>
    <p>สวัสดีคุณ {user_name},</p>
    <p>การจองของคุณได้รับการยืนยันเรียบร้อยแล้ว</p>
    <table>
      <tr><td><strong>โต๊ะ</strong></td><td>{table_number}</td></tr>
      <tr><td><strong>เริ่ม</strong></td><td>{_fmt(start_time)}</td></tr>
      <tr><td><strong>สิ้นสุด</strong></td><td>{_fmt(end_time)}</td></tr>
      <tr><td><strong>จำนวนคน</strong></td><td>{party_size}</td></tr>
    </table>
    <p>ขอบคุณที่ใช้บริการ</p>
    """
    _send(user_email, "ยืนยันการจองโต๊ะ - Restaurant Booking", html)


def send_booking_updated(
    user_email: str,
    user_name: str,
    table_number: str,
    start_time: datetime,
    end_time: datetime,
    party_size: int,
) -> None:
    html = f"""
    <h2>อัปเดตการจองโต๊ะ</h2>
    <p>สวัสดีคุณ {user_name},</p>
    <p>การจองของคุณได้รับการแก้ไขแล้ว</p>
    <table>
      <tr><td><strong>โต๊ะ</strong></td><td>{table_number}</td></tr>
      <tr><td><strong>เริ่ม</strong></td><td>{_fmt(start_time)}</td></tr>
      <tr><td><strong>สิ้นสุด</strong></td><td>{_fmt(end_time)}</td></tr>
      <tr><td><strong>จำนวนคน</strong></td><td>{party_size}</td></tr>
    </table>
    <p>ขอบคุณที่ใช้บริการ</p>
    """
    _send(user_email, "อัปเดตการจองโต๊ะ - Restaurant Booking", html)


def send_booking_cancelled(
    user_email: str,
    user_name: str,
    table_number: str,
    start_time: datetime,
) -> None:
    html = f"""
    <h2>ยกเลิกการจองโต๊ะ</h2>
    <p>สวัสดีคุณ {user_name},</p>
    <p>การจองต่อไปนี้ถูกยกเลิกเรียบร้อยแล้ว</p>
    <table>
      <tr><td><strong>โต๊ะ</strong></td><td>{table_number}</td></tr>
      <tr><td><strong>วันเวลา</strong></td><td>{_fmt(start_time)}</td></tr>
    </table>
    <p>หากมีข้อสงสัยกรุณาติดต่อเรา</p>
    """
    _send(user_email, "ยกเลิกการจองโต๊ะ - Restaurant Booking", html)
