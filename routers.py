import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request
import controllers
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta

router = APIRouter()

SECRET_KEY = "your-secret-key"  # เปลี่ยนเป็นคีย์ที่ปลอดภัย
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # เวลาหมดอายุของ JWT


# ฟังก์ชันสำหรับสร้าง JWT
def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ฟังก์ชันสำหรับตรวจสอบ JWT
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency เพื่อใช้ในการยืนยัน JWT
def get_current_user(token: str = Depends(verify_token)):
    return token


@router.post("/login")
def login(user: controllers.User):
    # สร้าง JWT เมื่อ login สำเร็จ
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/callback/")
async def read_callback(request: Request, state: str = None, code: str = None):
    return await controllers.health_id(code, state, request)


@router.post("/check/token/")
async def check_token(request: controllers.CheckTokenBase):
    return await controllers.token_check(request)
