import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ml_api.config import settings


async def send_verification_email(to_email: str, code: str):
    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = f"AInterior — код подтверждения: {code}"

    html_body = f"""\
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            max-width:480px;margin:0 auto;padding:40px 20px;">
  <h2 style="color:#48372F;margin-bottom:8px;">AInterior</h2>
  <p style="color:#666;font-size:15px;margin-bottom:24px;">
    Код подтверждения для вашего аккаунта:
  </p>
  <div style="background:#F4F3EE;border:2px solid #6D6943;border-radius:12px;
              padding:24px;text-align:center;margin-bottom:24px;">
    <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#6D6943;">
      {code}
    </span>
  </div>
  <p style="color:#999;font-size:13px;">
    Код действителен 10 минут. Если вы не запрашивали код — проигнорируйте это письмо.
  </p>
</div>"""

    message.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        use_tls=True,
    )
