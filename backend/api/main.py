def main():
    print("Hello from backend!")


if __name__ == "__main__":
    main()


from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from src.upload.router import router as upload_router
from src.ask.router import router as ask_router
from config.db import get_db

app = FastAPI()

app.include_router(upload_router)
app.include_router(ask_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)


@app.get('/health')
def get_health(db: Session = Depends(get_db)):
    print('get health')
    db.execute(text("SELECT 1")).scalar_one()
    return {
        'message': 'Health is ok'
    }