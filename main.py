from typing import Annotated
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from i18n import Translator, get_translator, load_catalog, SUPPORTED_LANGUAGES, ERROR_MESSAGES, VALIDATION_MESSAGES
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
    for language in SUPPORTED_LANGUAGES:
        load_catalog(language)
    yield


app = FastAPI(title="Expense Manager", lifespan=lifespan, dependencies=[Depends(require_csrf)])
app.include_router(auth_router)


@app.exception_handler(AuthError)
async def auth_error(request: Request, error: AuthError):
    translator = get_translator(request)
    response = JSONResponse(status_code=401, content={"detail": error.code, "message": translator.gettext(ERROR_MESSAGES.get(error.code, "The request could not be completed."))})
    if error.clear:
        clear_cookies(response)
    return response


@app.exception_handler(StarletteHTTPException)
async def localized_http_error(request: Request, error: StarletteHTTPException):
    translator = get_translator(request)
    source = ERROR_MESSAGES.get(str(error.detail), "The request could not be completed.")
    return JSONResponse(status_code=error.status_code,
                        content={"detail": error.detail, "message": translator.gettext(source)},
                        headers=error.headers)


@app.exception_handler(RequestValidationError)
async def localized_validation_error(request: Request, error: RequestValidationError):
    translator = get_translator(request)
    details = [{"type": item["type"], "loc": list(item["loc"]),
                "msg": translator.gettext(VALIDATION_MESSAGES.get(item["type"], "The value is invalid."))}
               for item in error.errors()]
    # Do not echo submitted passwords or other request input in error responses.
    return JSONResponse(status_code=422, content={"detail": details,
                        "message": translator.gettext("Some input fields are invalid.")})


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Content-Language"] = get_translator(request).language
    vary = [value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()]
    if "accept-language" not in {value.lower() for value in vary}:
        vary.append("Accept-Language")
    response.headers["Vary"] = ", ".join(vary)
    return response


AuthenticatedUser = Annotated[User, Depends(current_user)]
DB = Annotated[Session, Depends(get_db)]
Language = Annotated[Translator, Depends(get_translator)]


@app.get("/health", include_in_schema=False)
def health(db: DB):
    db.execute(select(Expense.id).limit(0))
    return {"status": "ok"}


@app.get("/welcome")
def welcome(translator: Language):
    return {"language": translator.language, "message": translator.gettext("Welcome to the expense manager.")}


@app.get("/about")
def about(translator: Language):
    return {"language": translator.language, "message": translator.gettext("This API manages your personal expenses.")}


@app.get("/expenses/summary")
def expense_summary(db: DB, user: AuthenticatedUser, translator: Language):
    count = db.scalar(select(func.count()).select_from(Expense).where(Expense.owner_id == user.id))
    message = translator.ngettext("You have %(count)d expense.", "You have %(count)d expenses.", count)
    return {"count": count, "message": message % {"count": count}, "language": translator.language}



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
