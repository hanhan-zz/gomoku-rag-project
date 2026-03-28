from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Request(BaseModel):
    a: float
    b: float
    op: str


@app.get("/")
def root():
    return {"message": "Calculator backend is running."}


@app.post("/calculate")
def calculate(req: Request):
    a, b, op = req.a, req.b, req.op
    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    elif op == "/":
        if b == 0:
            return {"result": "Error: division by zero"}
        result = a / b
    else:
        return {"result": f"Error: unknown operator '{op}'"}
    return {"result": round(result, 10)}
