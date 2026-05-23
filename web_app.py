"""职探AI Web 应用入口。"""

from __future__ import annotations

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
