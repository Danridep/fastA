from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from app.database import get_db_cursor
from app.models import User, UserCreate, UserUpdate, Token, BaseResponse
from app.config import settings

router = APIRouter()

# Настройки безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Получить текущего пользователя из токена"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истек"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные"
        )

    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден"
            )

        return User(**user)


@router.post("/register", response_model=BaseResponse)
async def register(user: UserCreate):
    """Регистрация нового пользователя"""
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование пользователя
            cursor.execute("SELECT id FROM users WHERE username = ?", (user.username,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким именем уже существует"
                )

            # Проверяем email если есть
            if user.email:
                cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Пользователь с таким email уже существует"
                    )

            # Создаем пользователя
            hashed_password = get_password_hash(user.password)
            cursor.execute(
                """
                INSERT INTO users (username, email, full_name, hashed_password)
                VALUES (?, ?, ?, ?)
                """,
                (user.username, user.email, user.full_name, hashed_password)
            )

            return BaseResponse(
                message="Пользователь успешно зарегистрирован",
                data={"id": cursor.lastrowid}
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка регистрации: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Авторизация пользователя"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (form_data.username,)
            )
            user = cursor.fetchone()

            if not user or not verify_password(form_data.password, user["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверное имя пользователя или пароль",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            access_token = create_access_token(
                data={"sub": user["username"]}
            )

            return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка авторизации: {str(e)}"
        )


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return current_user


@router.put("/me", response_model=BaseResponse)
async def update_current_user(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_user)
):
    """Обновить информацию о текущем пользователе"""
    try:
        with get_db_cursor() as cursor:
            update_fields = []
            params = []

            if user_update.username and user_update.username != current_user.username:
                # Проверяем уникальность нового имени
                cursor.execute(
                    "SELECT id FROM users WHERE username = ? AND id != ?",
                    (user_update.username, current_user.id)
                )
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Пользователь с таким именем уже существует"
                    )
                update_fields.append("username = ?")
                params.append(user_update.username)

            if user_update.email and user_update.email != current_user.email:
                # Проверяем уникальность нового email
                cursor.execute(
                    "SELECT id FROM users WHERE email = ? AND id != ?",
                    (user_update.email, current_user.id)
                )
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Пользователь с таким email уже существует"
                    )
                update_fields.append("email = ?")
                params.append(user_update.email)

            if user_update.full_name:
                update_fields.append("full_name = ?")
                params.append(user_update.full_name)

            if user_update.password:
                hashed_password = get_password_hash(user_update.password)
                update_fields.append("hashed_password = ?")
                params.append(hashed_password)

            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(current_user.id)

                query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
                cursor.execute(query, params)

            return BaseResponse(message="Данные пользователя обновлены")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления данных: {str(e)}"
        )


@router.post("/logout", response_model=BaseResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """Выход из системы"""
    return BaseResponse(message="Успешный выход из системы")