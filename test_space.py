from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI()

@app.get("/test")
def test():
    return RedirectResponse("http://localhost:5173/dashboard?token=123&name=John Doe&uid=456")
