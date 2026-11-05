from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_payment_service
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/compliance", operation_id="listPaymentCompliance")
def list_payment_compliance(
    search: Optional[str] = None,
    status: Optional[str] = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    service: PaymentService = Depends(get_payment_service),
) -> Dict[str, Any]:
    return service.list_cases(search=search, status=status, page=page, page_size=page_size)
