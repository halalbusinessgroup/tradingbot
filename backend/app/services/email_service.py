"""Email service — verification codes and trade notifications."""
import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

log = logging.getLogger(__name__)


def generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _template(title: str, content: str) -> str:
    return f"""
    <html><body style="font-family:sans-serif;background:#0b0e14;color:#e6edf3;padding:40px">
      <div style="max-width:480px;margin:auto;background:#11151d;border-radius:12px;padding:32px">
        <h2 style="color:#22c55e;margin-top:0">⚡ TradingBot</h2>
        <h3 style="color:#e6edf3;margin-top:0">{title}</h3>
        {content}
        <hr style="border:none;border-top:1px solid #1e2a1e;margin:24px 0">
        <p style="color:#555;font-size:11px">
          TradingBot platformasından göndərilmişdir. Siz bu bildirişi söndürə bilərsiniz — Tənzimlər → Email Bildirişlər.
        </p>
      </div>
    </body></html>
    """


def _send(to_email: str, subject: str, html_body: str) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        log.warning("SMTP konfiqurasiya edilməyib — email göndərilmir")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        log.info(f"Email göndərildi: {to_email} — {subject}")
        return True
    except Exception as e:
        log.error(f"Email xəta ({to_email}): {e}")
        return False


# ── Verification ────────────────────────────────────────────────────────────

def send_verification_email(to_email: str, code: str, purpose: str = "verification") -> bool:
    body = _template(
        "Doğrulama Kodu",
        f"""
        <p>Hesabınızın doğrulama kodu:</p>
        <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#22c55e;
                    margin:24px 0;text-align:center;background:#0b1a0f;padding:16px;border-radius:8px">
          {code}
        </div>
        <p style="color:#888;font-size:13px">Bu kod 10 dəqiqə ərzində etibarlıdır.</p>
        """
    )
    return _send(to_email, "⚡ TradingBot — Doğrulama Kodu", body)


# ── Trade Notifications ──────────────────────────────────────────────────────

def send_trade_opened(user_email: str, symbol: str, qty: float,
                      entry: float, tp: float, sl: float, paper: bool = False) -> bool:
    tag = "📄 Paper" if paper else "✅ Real"
    body = _template(
        f"{tag} Trade Açıldı",
        f"""
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr>
            <td style="color:#888;padding:6px 0">Symbol</td>
            <td style="font-weight:bold;color:#e6edf3">{symbol}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Giriş Qiyməti</td>
            <td style="font-weight:bold">{entry:.6f}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Miqdar</td>
            <td>{qty:.6f}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Take Profit</td>
            <td style="color:#22c55e;font-weight:bold">{tp:.6f}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Stop Loss</td>
            <td style="color:#ef4444;font-weight:bold">{sl:.6f}</td>
          </tr>
        </table>
        <a href="{settings.FRONTEND_URL}/dashboard"
           style="display:inline-block;margin:16px 0;padding:10px 20px;background:#22c55e;
                  color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
          Dashboard →
        </a>
        """
    )
    return _send(user_email, f"⚡ TradingBot — {symbol} Trade Açıldı", body)


def send_trade_closed(user_email: str, symbol: str, exit_price: float,
                      pnl: float, pnl_pct: float, reason: str, paper: bool = False) -> bool:
    pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
    pnl_sign = "+" if pnl >= 0 else ""
    reason_map = {
        "TP": "🎯 Take Profit",
        "SL": "🛡 Stop Loss",
        "MANUAL": "🔒 Manuel Bağlama",
    }
    reason_str = reason_map.get(reason, reason)
    tag = "📄 Paper" if paper else ""

    body = _template(
        f"{tag} Trade Bağlandı — {reason_str}",
        f"""
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr>
            <td style="color:#888;padding:6px 0">Symbol</td>
            <td style="font-weight:bold;color:#e6edf3">{symbol}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Çıxış Qiyməti</td>
            <td style="font-weight:bold">{exit_price:.6f}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">PnL</td>
            <td style="color:{pnl_color};font-weight:bold;font-size:18px">
              {pnl_sign}{pnl:.4f} USDT ({pnl_sign}{pnl_pct:.2f}%)
            </td>
          </tr>
          <tr>
            <td style="color:#888;padding:6px 0">Bağlanma Səbəbi</td>
            <td>{reason_str}</td>
          </tr>
        </table>
        <a href="{settings.FRONTEND_URL}/trades"
           style="display:inline-block;margin:16px 0;padding:10px 20px;background:#22c55e;
                  color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
          Trade Tarixçəsi →
        </a>
        """
    )
    return _send(user_email, f"⚡ TradingBot — {symbol} {reason_str}", body)


def send_bot_error(user_email: str, error_msg: str, symbol: str = "") -> bool:
    body = _template(
        "⚠️ Bot Xətası",
        f"""
        <p>Bot-unuzda xəta baş verdi:</p>
        <div style="background:#1a0505;border:1px solid #ef4444;border-radius:8px;
                    padding:16px;margin:16px 0;font-family:monospace;font-size:13px;color:#ef4444">
          {error_msg}
        </div>
        {"<p>Symbol: <strong>" + symbol + "</strong></p>" if symbol else ""}
        <a href="{settings.FRONTEND_URL}/dashboard"
           style="display:inline-block;margin:16px 0;padding:10px 20px;background:#22c55e;
                  color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
          Bot Loglarına Bax →
        </a>
        """
    )
    return _send(user_email, "⚡ TradingBot — Bot Xətası", body)
