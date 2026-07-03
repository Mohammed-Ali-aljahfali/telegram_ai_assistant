"""telethon_client/auth_handler.py — معالج مصادقة Telethon"""
import asyncio
from typing import Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    SessionPasswordNeededError, PasswordHashInvalidError,
    PhoneNumberInvalidError, FloodWaitError
)
from config import config
from infrastructure.logger import get_logger
from infrastructure.crypto import encrypt_text, decrypt_text

logger = get_logger("telethon.auth")

# تخزين مؤقت أثناء عملية التسجيل
_pending_auth: dict[int, dict] = {}


class TelethonAuthHandler:

    def __init__(self):
        self._temp_clients: dict[int, TelegramClient] = {}

    async def send_code(self, bot_user_id: int, phone: str) -> tuple[bool, str]:
        """إرسال رمز التحقق — يُرجع (success, message)"""
        try:
            client = TelegramClient(
                StringSession(), config.API_ID, config.API_HASH
            )
            await client.connect()

            result = await client.send_code_request(phone)

            _pending_auth[bot_user_id] = {
                "phone": phone,
                "phone_code_hash": result.phone_code_hash,
                "client": client,
            }
            self._temp_clients[bot_user_id] = client
            logger.info(f"✅ رمز أُرسل لـ {phone}")
            return True, result.phone_code_hash

        except PhoneNumberInvalidError:
            return False, "❌ رقم الجوال غير صحيح."
        except FloodWaitError as e:
            return False, f"⏳ انتظر {e.seconds} ثانية قبل المحاولة."
        except Exception as e:
            logger.error(f"send_code error: {e}")
            return False, f"❌ خطأ: {e}"

    async def verify_code(self, bot_user_id: int, code: str
                          ) -> tuple[bool, bool, str]:
        """التحقق من الرمز — يُرجع (success, needs_2fa, session_or_msg)"""
        data = _pending_auth.get(bot_user_id)
        if not data:
            return False, False, "❌ انتهت الجلسة. أعد المحاولة."

        client: TelegramClient = data["client"]
        try:
            await client.sign_in(
                data["phone"], code,
                phone_code_hash=data["phone_code_hash"]
            )
            session = client.session.save()
            await client.disconnect()
            _pending_auth.pop(bot_user_id, None)
            return True, False, session

        except SessionPasswordNeededError:
            return False, True, "needs_2fa"

        except (PhoneCodeInvalidError, PhoneCodeExpiredError):
            return False, False, "❌ الرمز غير صحيح أو منتهي."

        except Exception as e:
            logger.error(f"verify_code error: {e}")
            return False, False, f"❌ خطأ: {e}"

    async def verify_2fa(self, bot_user_id: int, password: str
                         ) -> tuple[bool, str]:
        """التحقق من كلمة مرور 2FA — يُرجع (success, session_or_msg)"""
        data = _pending_auth.get(bot_user_id)
        if not data:
            return False, "❌ انتهت الجلسة."

        client: TelegramClient = data["client"]
        try:
            await client.sign_in(password=password)
            session = client.session.save()
            await client.disconnect()
            _pending_auth.pop(bot_user_id, None)
            return True, session

        except PasswordHashInvalidError:
            return False, "❌ كلمة المرور غير صحيحة."
        except Exception as e:
            logger.error(f"verify_2fa error: {e}")
            return False, f"❌ خطأ: {e}"

    async def logout(self, bot_user_id: int, session_string: str) -> bool:
        """تسجيل الخروج"""
        try:
            client = TelegramClient(
                StringSession(decrypt_text(session_string)),
                config.API_ID, config.API_HASH
            )
            await client.connect()
            await client.log_out()
            return True
        except Exception as e:
            logger.error(f"logout error: {e}")
            return False

    async def get_account_info(self, session_string: str) -> Optional[dict]:
        """جلب معلومات الحساب"""
        try:
            decrypted = decrypt_text(session_string)
            client = TelegramClient(
                StringSession(decrypted), config.API_ID, config.API_HASH
            )
            await client.connect()
            me = await client.get_me()
            has_2fa = False
            try:
                pwd = await client(
                    __import__("telethon.tl.functions.account", fromlist=["GetPasswordRequest"]).GetPasswordRequest()
                )
                has_2fa = pwd.has_password
            except Exception:
                pass
            await client.disconnect()
            return {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "has_2fa": has_2fa,
            }
        except Exception as e:
            logger.error(f"get_account_info error: {e}")
            return None

    def cancel_auth(self, bot_user_id: int):
        """إلغاء عملية التسجيل"""
        data = _pending_auth.pop(bot_user_id, None)
        if data and "client" in data:
            asyncio.create_task(data["client"].disconnect())
