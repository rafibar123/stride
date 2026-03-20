"""Railway entry point — reads PORT from environment and starts uvicorn."""
import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[start] Starting server on port {port}", flush=True)

    try:
        import uvicorn
    except ImportError as e:
        print(f"[start] FATAL: cannot import uvicorn: {e}", flush=True)
        sys.exit(1)

    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
