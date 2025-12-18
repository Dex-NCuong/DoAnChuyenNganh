import sys
import io

# CRITICAL FIX: Set UTF-8 encoding and wrap stdout/stderr on Windows BEFORE any other imports
if sys.platform == 'win32':
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Wrap stdout and stderr to handle Unicode encoding errors at the stream level
    class SafeStreamWrapper:
        """Wrapper for stdout/stderr that handles Unicode encoding errors."""
        def __init__(self, original_stream):
            self._original = original_stream
            self._buffer = original_stream.buffer if hasattr(original_stream, 'buffer') else None
        
        def write(self, s):
            if isinstance(s, str):
                # Replace emojis before writing
                replacements = {
                    '🎯': '[TARGET]', '🔀': '[MULTI]', '📝': '[EXERCISE]',
                    '✅': '[OK]', '⚠️': '[WARN]', '🔧': '[FIX]',
                    '🛡️': '[SHIELD]', '⚖️': '[BALANCE]', '❌': '[ERROR]',
                    '🚀': '[ROCKET]', '📑': '[DOC]', '🪜': '[LADDER]',
                    '📊': '[CHART]', '🔄': '[RELOAD]', '📚': '[BOOKS]',
                }
                for emoji, replacement in replacements.items():
                    s = s.replace(emoji, replacement)
                # Try to write safely
                try:
                    return self._original.write(s)
                except UnicodeEncodeError:
                    # Fallback: encode to ASCII
                    s_safe = s.encode('ascii', errors='replace').decode('ascii')
                    return self._original.write(s_safe)
            else:
                return self._original.write(s)
        
        def __getattr__(self, name):
            return getattr(self._original, name)
    
    # Try to reconfigure stdout/stderr to UTF-8 first
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass
    
    # Wrap stdout and stderr
    sys.stdout = SafeStreamWrapper(sys.stdout)
    sys.stderr = SafeStreamWrapper(sys.stderr)
    
    # CRITICAL FIX: Monkey-patch built-in print to handle Unicode encoding errors
    import builtins
    _original_print = builtins.print
    def _safe_print_wrapper(*args, **kwargs):
        """Wrapper for built-in print that handles Unicode encoding errors."""
        try:
            # Try to replace emojis before printing
            msg_parts = []
            for arg in args:
                arg_str = str(arg)
                # Replace common emojis
                replacements = {
                    '🎯': '[TARGET]', '🔀': '[MULTI]', '📝': '[EXERCISE]',
                    '✅': '[OK]', '⚠️': '[WARN]', '🔧': '[FIX]',
                    '🛡️': '[SHIELD]', '⚖️': '[BALANCE]', '❌': '[ERROR]',
                    '🚀': '[ROCKET]', '📑': '[DOC]', '🪜': '[LADDER]',
                    '📊': '[CHART]', '🔄': '[RELOAD]', '📚': '[BOOKS]',
                }
                for emoji, replacement in replacements.items():
                    arg_str = arg_str.replace(emoji, replacement)
                msg_parts.append(arg_str)
            msg = ' '.join(msg_parts)
            # Try to encode to test if it's safe
            try:
                msg.encode('cp1252', errors='strict')
                _original_print(msg, **kwargs)
            except (UnicodeEncodeError, LookupError):
                msg_safe = msg.encode('ascii', errors='replace').decode('ascii')
                _original_print(msg_safe, **kwargs)
        except Exception:
            # Ultimate fallback: encode everything to ASCII
            try:
                msg = ' '.join(str(arg).encode('ascii', errors='replace').decode('ascii') for arg in args)
                _original_print(msg, **kwargs)
            except:
                pass
    builtins.print = _safe_print_wrapper

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .core.config import settings

# Safe print function to handle Unicode encoding errors on Windows
def safe_print(*args, **kwargs):
    """Print function that handles Unicode encoding errors gracefully."""
    # PROACTIVE FIX: Replace emojis BEFORE trying to print to avoid encoding errors
    try:
        # Get the string representation first, handling encoding errors during conversion
        msg_parts = []
        for arg in args:
            try:
                arg_str = str(arg)
            except UnicodeEncodeError:
                # If str() itself fails, encode with errors='replace'
                try:
                    arg_str = repr(arg).encode('ascii', errors='replace').decode('ascii')
                except:
                    arg_str = "[Unable to convert to string]"
            
            # Replace common emojis with ASCII equivalents BEFORE printing
            replacements = {
                '🎯': '[TARGET]',
                '🔀': '[MULTI]',
                '📝': '[EXERCISE]',
                '✅': '[OK]',
                '⚠️': '[WARN]',
                '🔧': '[FIX]',
                '🛡️': '[SHIELD]',
                '⚖️': '[BALANCE]',
                '❌': '[ERROR]',
                '🚀': '[ROCKET]',
                '📑': '[DOC]',
                '🪜': '[LADDER]',
                '📊': '[CHART]',
                '🔄': '[RELOAD]',
                '📚': '[BOOKS]',
            }
            for emoji, replacement in replacements.items():
                arg_str = arg_str.replace(emoji, replacement)
            msg_parts.append(arg_str)
        
        # Join and encode to ensure Windows console compatibility
        msg = ' '.join(msg_parts)
        # Try to encode to ensure it's safe for Windows console
        try:
            # Test encoding to Windows console default (usually cp1252 or similar)
            msg.encode('cp1252', errors='strict')
            # If successful, print normally
            print(msg, **kwargs)
        except (UnicodeEncodeError, LookupError):
            # If cp1252 fails, use ASCII with replacement
            msg_safe = msg.encode('ascii', errors='replace').decode('ascii')
            print(msg_safe, **kwargs)
    except UnicodeEncodeError as e:
        # Fallback: encode to ASCII with errors='replace'
        try:
            msg = ' '.join(str(arg).encode('ascii', errors='replace').decode('ascii') for arg in args)
            print(msg, **kwargs)
        except Exception as e2:
            # Ultimate fallback: just print error message
            try:
                print(f"[safe_print] Error: {e2}", **kwargs)
            except:
                pass
    except Exception as e:
        # Fallback: try to print anyway with safe encoding
        try:
            msg = ' '.join(str(arg).encode('ascii', errors='replace').decode('ascii') for arg in args)
            print(msg, **kwargs)
        except:
            pass



def create_app() -> FastAPI:
    app = FastAPI(title="AI Study QnA", version="0.1.0")

    # CORS configuration - must be before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,  # avoid "*" when allow_credentials=True
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/hello")
    async def hello():
        return {"message": "Hello from FastAPI"}

    # Global exception handler for unhandled exceptions (not HTTPException)
    # This ensures CORS headers are always included even when unexpected errors occur
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Let FastAPI handle HTTPException (it already includes CORS headers via middleware)
        if isinstance(exc, HTTPException):
            raise exc
        
        safe_print(f"[Global Exception Handler] {type(exc).__name__}: {str(exc)}")
        import traceback
        safe_print(f"[Global Exception Handler] Traceback: {traceback.format_exc()}")

        # IMPORTANT: Do not manually manage CORS headers here.
        # CORSMiddleware will attach the correct headers (including on 500 responses).
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": f"Lỗi server: {str(exc)}"
            },
        )

    # Routers (Module 3+)
    from .routers import auth, documents, query, history, admin, calendar, quiz

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(query.router, prefix="/query", tags=["query"])
    app.include_router(history.router, prefix="/history", tags=["history"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
    app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])

    return app


app = create_app()


