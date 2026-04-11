from fastapi.responses import JSONResponse


def success(data: dict | list) -> dict:
    return {"success": True, "data": data}


def success_list(data: list, page: int, per_page: int, total: int) -> dict:
    return {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": -(-total // per_page),
        },
    }


def error(code: str, message: str, detail: dict | None = None, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message, "detail": detail or {}},
        },
    )
