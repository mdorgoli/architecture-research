from typing import Annotated
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Expense, User
from auth import router as auth_router
from security import AuthError, clear_cookies, current_user, require_csrf
from settings import get_settings
from schemas import ExpenseInput, ExpenseOutput

@asynccontextmanager
async def lifespan(app):
    get_settings()  # Refuse to start without a signing secret and HTTPS origin.
    yield


app = FastAPI(title="Expense Manager", lifespan=lifespan, dependencies=[Depends(require_csrf)])
app.include_router(auth_router)


@app.exception_handler(AuthError)
async def auth_error(request: Request, error: AuthError):
    response = JSONResponse(status_code=401, content={"detail": error.code})
    if error.clear:
        clear_cookies(response)
    return response


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


AuthenticatedUser = Annotated[User, Depends(current_user)]
DB = Annotated[Session, Depends(get_db)]


def find_expense(expense_id: int, db: Session, user_id: int) -> Expense:
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.owner_id == user_id))
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@app.post("/expenses", response_model=ExpenseOutput, status_code=status.HTTP_201_CREATED)
def create_expense(data: ExpenseInput, db: DB, user: AuthenticatedUser):
    expense = Expense(owner_id=user.id, **data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/expenses", response_model=list[ExpenseOutput])
def list_expenses(db: DB, user: AuthenticatedUser):
    return db.scalars(select(Expense).where(Expense.owner_id == user.id).order_by(Expense.id)).all()


@app.get("/expenses/{expense_id}", response_model=ExpenseOutput)
def get_expense(expense_id: int, db: DB, user: AuthenticatedUser):
    return find_expense(expense_id, db, user.id)


@app.put("/expenses/{expense_id}", response_model=ExpenseOutput)
def update_expense(expense_id: int, data: ExpenseInput, db: DB, user: AuthenticatedUser):
    expense = find_expense(expense_id, db, user.id)
    expense.description = data.description
    expense.amount = data.amount
    db.commit()
    db.refresh(expense)
    return expense


@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DB, user: AuthenticatedUser):
    expense = find_expense(expense_id, db, user.id)
    db.delete(expense)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
