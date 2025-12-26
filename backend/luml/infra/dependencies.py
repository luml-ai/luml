from fastapi import HTTPException, Request, status


class UserAuthentication:
    def __init__(self, scopes: list[str]) -> None:
        self.scopes = scopes

    def __call__(self, request: Request) -> None:
        if not request.user.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        if not any(scope in request.auth.scopes for scope in self.scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires "
                f"{', '.join(self.scopes)} authentication.",
            )
