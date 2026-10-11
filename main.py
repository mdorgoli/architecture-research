from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Expense
from schemas import ExpenseInput, ExpenseOutput

app = FastAPI(title="Expense Manager")
DB = Annotated[Session, Depends(get_db)]


def find_expense(expense_id: int, db: Session) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@app.post("/expenses", response_model=ExpenseOutput, status_code=status.HTTP_201_CREATED)
def create_expense(data: ExpenseInput, db: DB):
    expense = Expense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/expenses", response_model=list[ExpenseOutput])
def list_expenses(db: DB):
    return db.scalars(select(Expense).order_by(Expense.id)).all()


@app.get("/expenses/{expense_id}", response_model=ExpenseOutput)
def get_expense(expense_id: int, db: DB):
    return find_expense(expense_id, db)


@app.put("/expenses/{expense_id}", response_model=ExpenseOutput)
def update_expense(expense_id: int, data: ExpenseInput, db: DB):
    expense = find_expense(expense_id, db)
    expense.description = data.description
    expense.amount = data.amount
    db.commit()
    db.refresh(expense)
    return expense


@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DB):
    expense = find_expense(expense_id, db)
    db.delete(expense)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
