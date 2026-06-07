import re

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")
        if not re.search(r"[A-Z]", v):
            raise ValueError("ต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว")
        if not re.search(r"[0-9]", v):
            raise ValueError("ต้องมีตัวเลขอย่างน้อย 1 ตัว")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("ต้องมีอักขระพิเศษอย่างน้อย 1 ตัว")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_length(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("ชื่อต้องมีอย่างน้อย 2 ตัวอักษร")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^0\d{9}$", v):
            raise ValueError("รูปแบบเบอร์โทรไม่ถูกต้อง (ตัวอย่าง: 0812345678)")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: dict
