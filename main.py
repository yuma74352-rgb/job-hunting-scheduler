import os
import json
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


load_dotenv()


if not firebase_admin._apps:
    firebase_creds_json = os.environ.get("FIREBASE_KEY")

    if firebase_creds_json:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        cred = credentials.Certificate(cred_path)

    firebase_admin.initialize_app(cred)

db = firestore.client()


app = FastAPI()
templates = Jinja2Templates(directory = "templates")


@app.get("/")
def read_root(request: Request):

    return templates.TemplateResponse(
        request = request,
        name = "index.html",
        context = {
            "firebase_api_key": os.getenv("FIREBASE_API_KEY")
        }
    )


@app.post("/get-events")
async def get_events(id_token: str = Form(...)):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="認証トークンが無効または期限切れです")

    firebase_events = []
    docs =db.collection("events").where("uid", "==", uid).stream()
    for doc in docs:
        event_data = doc.to_dict()
        event_data["id"] = doc.id
        firebase_events.append(event_data)

    sorted_events = sorted(firebase_events, key=lambda x: (x.get("date", ""), x.get("time", "")))

    return {"events": sorted_events}

@app.post("/add")
async def add_event(
    id_token: str = Form(...),
    event_name: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    event_tag: str = Form(...),
    priority: str = Form(...)
):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
    
    except Exception:
        raise HTTPException(status_code=401, detail="認証トークンが無効または期限切れです")

    new_event = {
        "uid": uid,
        "date": event_date,
        "time": event_time,
        "name": event_name,
        "tag": event_tag,
        "priority": priority
    }
    db.collection("events").add(new_event)

    return RedirectResponse(url = "/", status_code = 303)


@app.post("/delete/{event_id}")
def delete_event(event_id: str, id_token: str = Form(None)):
    if not id_token:
        raise HTTPException(status_code=401, detail="認証トークンが必要です")
    
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="認証トークンが無効です")
 
    doc_ref = db.collection("events").document(event_id)
    doc = doc_ref.get()

    if doc.exists and doc.to_dict().get("uid") == uid:
        doc_ref.delete()
    else:
        raise HTTPException(status_code=403, detail="他人の予定は削除できません")
    
    return RedirectResponse(url="/", status_code=303)