from pydantic import BaseModel, ConfigDict, Field


class ExpenseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str = Field(min_length=1, strict=True)
    amount: float = Field(gt=0, allow_inf_nan=False, strict=True)


class ExpenseOutput(ExpenseInput):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0, strict=True)
