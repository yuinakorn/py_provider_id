import json
import urllib
import jwt
import datetime
import httpx
import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# โหลดค่าจากไฟล์ .env
load_dotenv()
app = FastAPI()


# เอา code ไปแลกเป็น access_token จาก health_id
async def health_id(code: str, state: str, request: Request):
    url = os.getenv("URL_HEALTH_ID")
    payload = {
        "grant_type": os.getenv("GRANT_TYPE"),
        "code": code,
        "client_id": os.getenv("HEALTH_CLIENT_ID"),
        "client_secret": os.getenv("HEALTH_CLIENT_SECRET"),
        "redirect_uri": os.getenv("REDIRECT_URI"),
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # Encode the payload
    encoded_payload = urllib.parse.urlencode(payload)

    # ทำ POST request ไปยัง URL ที่กำหนด
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, data=encoded_payload)

    # ตรวจสอบว่า response ส่งกลับมาถูกต้องหรือไม่
    if response.status_code == 200:
        print({"message": "ก่อนส่งไป provider", "data": response.json()})
        json_response = response.json()
        health_access_token = response.json()["data"]["access_token"]
        decoded_token = jwt.decode(health_access_token, options={"verify_signature": False})

        # ดึงค่า id_card จาก scopes_detail
        id_card = decoded_token["scopes_detail"]["id_card"]

        print({"message": "decoded_token", "data": decoded_token})

        # เรียกฟังก์ชัน provider_id โดยส่ง access_token
        provider_response = await provider_id(health_access_token, id_card, state, request)
        return provider_response
    else:
        return {"message": "Request failed", "status_code": response.json()}


# ฟังก์ชัน provider_id ที่จะรับ access_token และทำการ POST ต่อไป
async def provider_id(health_access_token: str, id_card: str, state: str, request: Request):
    url = os.getenv("URL_SERVICE_PROVIDER")  # URL ของ provider ที่ต้องการเรียก

    payload = {
        "client_id": os.getenv("PROV_CLIENT_ID"),
        "secret_key": os.getenv("PROV_CLIENT_SECRET"),
        "token_by": os.getenv("TOKEN_BY"),
        "token": health_access_token,
    }

    print({"message": "ใน provider_id()", "data": payload})

    headers = {
        'Authorization': f'Bearer {health_access_token}',
        'Content-Type': 'application/json'
    }

    # ส่ง POST request ไปยัง provider
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    # ตรวจสอบสถานะของการตอบกลับ
    if response.status_code == 200:
        json_response = response.json()
        provider_access_token = response.json()["data"]["access_token"]
        # เรียกฟังก์ชัน get_final_data เพื่อเอาข้อมูลดิบของ provider
        response_profile = await get_profile_data(provider_access_token, id_card, state, request)
        return response_profile
    else:
        return {"message": "Provider request failed", "error": response.status_code}


async def get_profile_data(provider_access_token: str, id_card: str, state: str, request: Request):
    print({"message": "ใน get_profile_data()", "access_token": provider_access_token})
    # split state with -
    state = state.split("-")
    redirect_uri = state[2]

    url = os.getenv("URL_PROFILE")
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {provider_access_token}',
        'client-id': os.getenv("PROV_CLIENT_ID"),
        'secret-key': os.getenv("PROV_CLIENT_SECRET"),
    }

    print({"headers ใน profile": headers})

    # GET request
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30)

    if response.status_code == 200:
        data = response.json()
        # สร้าง organization ใหม่ที่มีเฉพาะ position และ hcode
        new_organization = [
            {"position": org["position"], "hcode": org["hcode"]}
            for org in data["data"]["organization"]
        ]
        new_profile = {
            "id_card": id_card,
            "firstname_th": data["data"]["firstname_th"],
            "lastname_th": data["data"]["lastname_th"],
            "organization": new_organization,
        }

        # Encode new_profile into JWT
        secret_key = os.getenv("JWT_SECRET_KEY")
        encoded_jwt = jwt.encode(
            {
                "profile": new_profile,
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5),
            },
            secret_key,
            algorithm="HS256"
        )

        context_data = {
            "redirect_uri": f"https://{redirect_uri}",  # get from state
            "jwt": encoded_jwt,
            "wait_time": 3,
            "title": state[0],
        }

        # return {"jwt": encoded_jwt}
        return templates.TemplateResponse("redirect.html", {"request": request, **context_data})
    else:
        return {"message": "Profile request failed", "error": response.json(), "url": url}


async def token_check(request):
    token = request.token
    secret_key = os.getenv("JWT_SECRET_KEY")
    try:
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        return {"message": "Token is valid", "data": decoded, "status": 200}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        return {"message": str(e)}


class CheckTokenBase(BaseModel):
    token: str

    class Config:
        orm_mode = True

    def get(self, key):
        return getattr(self, key, None)


class User(BaseModel):
    username: str
    password: str
